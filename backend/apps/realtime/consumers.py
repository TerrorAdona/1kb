from urllib.parse import parse_qs
import json

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from django.conf import settings
from redis.asyncio import Redis

from apps.games.models import Game, GameParticipant
from apps.games.serializers import GameReadSerializer

class GameLobbyConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        self.game_id = self.scope["url_route"]["kwargs"]["game_id"]
        self.group_name = f"game_{str(self.game_id).replace('-', '')}"
        ticket_values = parse_qs(
            self.scope.get("query_string", b"").decode("utf-8")
        ).get("ticket", [])
        if not ticket_values:
            await self.close(code=4401)
            return

        try:
            user_id = await self._consume_ticket(ticket_values[0])
        except Exception:
            await self.close(code=4401)
            return
        if (
            not user_id
            or str(self.game_id) != user_id["game_id"]
            or not await self._is_participant(user_id["user_id"])
        ):
            await self.close(code=4403)
            return
        self.user_id = int(user_id["user_id"])

        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()
        snapshot = await self._get_snapshot()
        if snapshot is None:
            await self.close(code=4404)
            return
        await self.send_json({"type": "lobby.snapshot", "game": snapshot})

    async def disconnect(self, close_code):
        if hasattr(self, "group_name"):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive_json(self, content, **kwargs):
        # Les actions de lobby passent par REST afin d’avoir un contrat et une
        # validation uniques ; le WebSocket ne fait que diffuser les changements.
        await self.send_json(
            {
                "type": "error",
                "code": "read_only_socket",
                "detail": "Utilisez l’API REST pour modifier le salon.",
            }
        )

    async def lobby_event(self, event):
        if not await self._is_participant(self.user_id):
            await self.close(code=4403)
            return
        payload = event["event"]
        await self.send_json(
            {
                "type": "lobby.event",
                "event": {
                    "id": payload["id"],
                    "sequence": payload["sequence"],
                    "event_type": payload["event_type"],
                    "actor_display_name": payload["actor_display_name"],
                    "data": payload["public"],
                    "private": payload.get("private", {}).get(str(self.user_id), {}),
                    "created_at": payload["created_at"],
                },
            }
        )

    async def _consume_ticket(self, ticket: str):
        # Redis GETDEL garantit qu’un ticket ne peut ouvrir qu’une seule socket.
        redis = Redis.from_url(settings.REDIS_URL, decode_responses=True)
        try:
            value = await redis.getdel(f"ws-ticket:{ticket}")
            return json.loads(value) if value else None
        finally:
            await redis.aclose()

    @database_sync_to_async
    def _is_participant(self, user_id):
        return GameParticipant.objects.filter(
            game_id=self.game_id, user_id=user_id
        ).exists()

    @database_sync_to_async
    def _get_snapshot(self):
        try:
            game = (
                Game.objects.select_related("host", "result__winner")
                .prefetch_related("participants")
                .get(pk=self.game_id)
            )
        except Game.DoesNotExist:
            return None
        return GameReadSerializer(game).data
