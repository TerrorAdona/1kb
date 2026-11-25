import asyncio
from contextlib import suppress
from json import JSONDecodeError
from time import time
from urllib.parse import parse_qs
from uuid import UUID

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from django.conf import settings
from redis.asyncio import Redis
from rest_framework.exceptions import APIException

from apps.accounts.models import User
from apps.games.services import (
    GameConflict,
    abandon_multiplayer_game,
    apply_multiplayer_action,
)
from .projections import get_participant_id, get_player_snapshot

PRESENCE_TTL_SECONDS = 90
PRESENCE_HEARTBEAT_SECONDS = 25
PRESENCE_STALE_AFTER_SECONDS = 75


class GameLobbyConsumer(AsyncJsonWebsocketConsumer):
    """Authenticated lobby and live-game socket for one participant."""

    async def connect(self):
        self.game_id = self.scope["url_route"]["kwargs"]["game_id"]
        self.group_name = f"game_{str(self.game_id).replace('-', '')}"
        self.user_id = None
        self.participant_id = None
        self.redis = None
        self._presence_task = None

        ticket_values = parse_qs(
            self.scope.get("query_string", b"").decode("utf-8")
        ).get("ticket", [])
        if len(ticket_values) != 1 or not ticket_values[0]:
            await self.close(code=4401)
            return

        try:
            ticket_payload = await self._consume_ticket(ticket_values[0])
        except (JSONDecodeError, TypeError, ValueError):
            await self.close(code=4401)
            return
        except Exception:
            await self.close(code=1013)
            return

        if (
            not isinstance(ticket_payload, dict)
            or str(ticket_payload.get("game_id")) != str(self.game_id)
        ):
            await self.close(code=4403)
            return
        try:
            self.user_id = int(ticket_payload["user_id"])
        except (KeyError, TypeError, ValueError):
            await self.close(code=4401)
            return

        self.participant_id = await database_sync_to_async(get_participant_id)(
            game_id=self.game_id, user_id=self.user_id
        )
        if self.participant_id is None:
            await self.close(code=4403)
            return
        self.participant_id = str(self.participant_id)

        try:
            self.redis = Redis.from_url(settings.REDIS_URL, decode_responses=True)
            await self._touch_presence()
            await self.channel_layer.group_add(self.group_name, self.channel_name)
            await self.accept()
        except Exception:
            if self.redis and self.participant_id:
                with suppress(Exception):
                    await self.redis.zrem(
                        self._presence_key(), self.channel_name
                    )
            await self._close_redis()
            await self.close(code=1013)
            return

        self._presence_task = asyncio.create_task(self._presence_heartbeat())
        snapshot = await self._get_snapshot()
        if snapshot is None:
            await self.close(code=4404)
            return
        await self._send_snapshot(snapshot)
        await self._broadcast_presence(online=True)

    async def disconnect(self, close_code):
        if self._presence_task:
            self._presence_task.cancel()
            with suppress(asyncio.CancelledError):
                await self._presence_task
            self._presence_task = None

        if getattr(self, "group_name", None):
            with suppress(Exception):
                await self.channel_layer.group_discard(
                    self.group_name, self.channel_name
                )

        if self.redis and self.participant_id:
            try:
                await self.redis.zrem(
                    self._presence_key(), self.channel_name
                )
                online = await self._is_online()
                if not online:
                    await self._broadcast_presence(online=False)
            except Exception:
                # The durable game snapshot remains available for reconnects.
                pass
        await self._close_redis()

    async def receive_json(self, content, **kwargs):
        if not isinstance(content, dict):
            await self._send_error("invalid_message", "Le message doit être un objet JSON.")
            return

        message_type = content.get("type")
        if message_type not in {"game.action", "game.abandon"}:
            await self._send_error(
                "unsupported_message",
                "Utilisez l’API REST pour gérer le salon ; seules les commandes de partie sont acceptées.",
            )
            return

        try:
            request_id = UUID(str(content.get("request_id", "")))
        except (TypeError, ValueError, AttributeError):
            await self._send_error("invalid_request_id", "Un request_id UUID est requis.")
            return

        try:
            user = await database_sync_to_async(User.objects.get)(pk=self.user_id)
            if message_type == "game.abandon":
                game, duplicate = await database_sync_to_async(
                    abandon_multiplayer_game
                )(
                    game_id=self.game_id,
                    user=user,
                    request_id=request_id,
                )
            else:
                action = content.get("action")
                card_id = content.get("card_id")
                target_player_id = content.get("target_player_id")
                expected_version = content.get("state_version")
                if not isinstance(action, str) or len(action) > 16:
                    await self._send_error("invalid_action", "Le type d’action est invalide.")
                    return
                if card_id is not None and (
                    not isinstance(card_id, str) or len(card_id) > 128
                ):
                    await self._send_error("invalid_card_id", "L’identifiant de carte est invalide.")
                    return
                if target_player_id is not None and (
                    not isinstance(target_player_id, str)
                    or len(target_player_id) > 128
                ):
                    await self._send_error(
                        "invalid_target", "L’identifiant de cible est invalide."
                    )
                    return
                if (
                    isinstance(expected_version, bool)
                    or not isinstance(expected_version, int)
                ):
                    await self._send_error(
                        "invalid_state_version",
                        "La version courante de la partie est requise.",
                    )
                    return
                game, duplicate = await database_sync_to_async(
                    apply_multiplayer_action
                )(
                    game_id=self.game_id,
                    user=user,
                    request_id=request_id,
                    expected_version=expected_version,
                    action=action,
                    card_id=card_id,
                    target_player_id=target_player_id,
                )
        except APIException as exc:
            await self._send_error(
                str(exc.get_codes()),
                str(exc.detail),
            )
            if isinstance(exc, GameConflict):
                snapshot = await self._get_snapshot()
                if snapshot is not None:
                    await self._send_snapshot(snapshot)
            return
        except Exception:
            await self._send_error(
                "server_error",
                "La commande n’a pas pu être traitée.",
            )
            return

        await self.send_json(
            {
                "type": "game.ack",
                "request_id": str(request_id),
                "state_version": game.state_version,
                "status": game.status,
                "duplicate": duplicate,
            }
        )

    async def lobby_event(self, event):
        if not await self._is_participant():
            await self.close(code=4403)
            return

        payload = event["event"]
        snapshot = await self._get_snapshot()
        if snapshot is None:
            await self.close(code=4404)
            return
        await self.send_json(
            {
                "type": "game.event",
                "event": {
                    "id": payload["id"],
                    "sequence": payload["sequence"],
                    "event_type": payload["event_type"],
                    "actor_display_name": payload["actor_display_name"],
                    "data": payload["public"],
                    "private": payload.get("private", {}).get(
                        str(self.user_id), {}
                    ),
                    "created_at": payload["created_at"],
                },
                **snapshot,
            }
        )

    async def presence_event(self, event):
        if not await self._is_participant():
            await self.close(code=4403)
            return
        await self.send_json(
            {
                "type": "presence.changed",
                "participant_id": event["participant_id"],
                "online": event["online"],
            }
        )

    async def _send_snapshot(self, snapshot):
        message_type = (
            "game.snapshot"
            if snapshot["game"]["status"]
            in {"active", "finished", "cancelled"}
            else "lobby.snapshot"
        )
        await self.send_json({"type": message_type, **snapshot})

    async def _send_error(self, code, detail):
        await self.send_json(
            {"type": "game.error", "code": code, "detail": detail}
        )

    async def _get_snapshot(self):
        snapshot = await database_sync_to_async(get_player_snapshot)(
            game_id=self.game_id, user_id=self.user_id
        )
        if snapshot is None:
            return None

        presence = {}
        for participant in snapshot["game"]["participants"]:
            if participant["kind"] != "human":
                continue
            participant_id = participant["id"]
            presence[participant_id] = await self._is_online(participant_id)
        snapshot["presence"] = presence
        return snapshot

    async def _is_participant(self):
        return bool(
            await database_sync_to_async(get_participant_id)(
                game_id=self.game_id, user_id=self.user_id
            )
        )

    def _presence_key(self, participant_id=None):
        participant_id = participant_id or self.participant_id
        return f"game-presence:{self.game_id}:{participant_id}"

    async def _touch_presence(self):
        now = time()
        key = self._presence_key()
        await self.redis.zremrangebyscore(
            key, "-inf", now - PRESENCE_STALE_AFTER_SECONDS
        )
        await self.redis.zadd(key, {self.channel_name: now})
        await self.redis.expire(key, PRESENCE_TTL_SECONDS)

    async def _is_online(self, participant_id=None):
        if not self.redis:
            return False
        key = self._presence_key(participant_id)
        await self.redis.zremrangebyscore(
            key, "-inf", time() - PRESENCE_STALE_AFTER_SECONDS
        )
        return bool(await self.redis.zcard(key))

    async def _presence_heartbeat(self):
        try:
            while True:
                await asyncio.sleep(PRESENCE_HEARTBEAT_SECONDS)
                try:
                    await self._touch_presence()
                except Exception:
                    # Retry on the next heartbeat; the TTL bounds stale presence.
                    continue
        except asyncio.CancelledError:
            raise

    async def _broadcast_presence(self, *, online):
        if not self.participant_id:
            return
        await self.channel_layer.group_send(
            self.group_name,
            {
                "type": "presence.event",
                "participant_id": self.participant_id,
                "online": online,
            },
        )

    async def _consume_ticket(self, ticket):
        redis = Redis.from_url(settings.REDIS_URL, decode_responses=True)
        try:
            value = await redis.getdel(f"ws-ticket:{ticket}")
            if not value:
                return None
            import json

            return json.loads(value)
        finally:
            await redis.aclose()

    async def _close_redis(self):
        if self.redis:
            redis, self.redis = self.redis, None
            with suppress(Exception):
                await redis.aclose()
