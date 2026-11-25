import asyncio
from collections import defaultdict
import json
from unittest.mock import AsyncMock, patch
from uuid import uuid4

from channels.layers import get_channel_layer
from django.test import TransactionTestCase, override_settings

from apps.accounts.models import User
from apps.games.models import Game, GameParticipant
from apps.games.services import (
    GameActionRejected,
    GameConflict,
    apply_multiplayer_action,
    start_game,
)
from .consumers import GameLobbyConsumer
from .projections import get_participant_id, get_player_snapshot


class FakeRedis:
    """Async sorted-set fake for testing per-connection presence."""

    def __init__(self):
        self.values = defaultdict(dict)

    async def zremrangebyscore(self, key, minimum, maximum):
        max_value = float("-inf") if maximum == "-inf" else float(maximum)
        expired = [
            member
            for member, score in self.values[key].items()
            if score <= max_value
        ]
        for member in expired:
            self.values[key].pop(member, None)
        return len(expired)

    async def zadd(self, key, mapping):
        self.values[key].update(mapping)
        return len(mapping)

    async def expire(self, key, seconds):
        return True

    async def zcard(self, key):
        return len(self.values[key])

    async def zrem(self, key, member):
        return int(self.values[key].pop(member, None) is not None)

    async def aclose(self):
        return None


def fake_database_sync_to_async(test_case, function):
    async def run(*args, **kwargs):
        if function is get_participant_id:
            return test_case.participant_ids.get(kwargs["user_id"])
        if function is get_player_snapshot:
            return test_case.snapshots[kwargs["user_id"]]
        if function.__name__ == "get" and "pk" in kwargs:
            return test_case.users[kwargs["pk"]]
        if function.__name__ == "apply_multiplayer_action":
            if kwargs["user"].pk == test_case.guest.pk:
                raise GameActionRejected("Ce n’est pas votre tour.", "not_your_turn")
            request_id = kwargs["request_id"]
            duplicate = request_id in test_case.request_results
            test_case.request_results.add(request_id)
            return test_case.game, duplicate
        if function.__name__ == "abandon_multiplayer_game":
            return test_case.game, False
        raise AssertionError(f"Unexpected database call: {function!r}")

    return run


async def threaded_is_participant(consumer):
    return consumer.user_id in consumer.scope["test_participant_ids"]


@override_settings(
    CHANNEL_LAYERS={
        "default": {"BACKEND": "channels.layers.InMemoryChannelLayer"}
    },
    FRONTEND_ORIGINS=["http://localhost:5173"],
)
class MultiplayerConsumerTests(TransactionTestCase):
    reset_sequences = True

    def setUp(self):
        self.assertEqual(
            type(get_channel_layer()).__name__, "InMemoryChannelLayer"
        )
        self.host = User.objects.create_user(
            "socket-host@example.com",
            "Valid-password-481!Card",
            display_name="Hôte",
        )
        self.guest = User.objects.create_user(
            "socket-guest@example.com",
            "Valid-password-481!Card",
            display_name="Invité",
        )
        self.stranger = User.objects.create_user(
            "socket-stranger@example.com",
            "Valid-password-481!Card",
            display_name="Visiteur",
        )
        self.game = Game.objects.create(
            host=self.host,
            mode=Game.Mode.MULTIPLAYER,
            visibility=Game.Visibility.PUBLIC,
            max_players=2,
        )
        self.host_seat = GameParticipant.objects.create(
            game=self.game,
            user=self.host,
            seat_number=1,
            display_name=self.host.display_name,
            is_ready=True,
        )
        self.guest_seat = GameParticipant.objects.create(
            game=self.game,
            user=self.guest,
            seat_number=2,
            display_name=self.guest.display_name,
            is_ready=True,
        )
        start_game(game_id=self.game.pk, user=self.host)
        self.game.refresh_from_db()
        self.users = {
            self.host.pk: self.host,
            self.guest.pk: self.guest,
            self.stranger.pk: self.stranger,
        }
        self.participant_ids = {
            self.host.pk: self.host_seat.pk,
            self.guest.pk: self.guest_seat.pk,
        }
        self.snapshots = {
            user.pk: get_player_snapshot(game_id=self.game.pk, user_id=user.pk)
            for user in (self.host, self.guest)
        }
        self.request_results = set()

    async def make_consumer(self, user, *, game_id=None, ticket_game_id=None):
        output = []

        async def capture(message):
            output.append(message)

        consumer = GameLobbyConsumer()
        consumer.scope = {
            "url_route": {"kwargs": {"game_id": game_id or self.game.pk}},
            "query_string": b"ticket=single-use-ticket",
            "test_participant_ids": set(self.participant_ids),
        }
        consumer.channel_layer = get_channel_layer()
        consumer.channel_name = await consumer.channel_layer.new_channel()
        consumer.base_send = capture
        consumer._consume_ticket = AsyncMock(
            return_value={
                "user_id": str(user.pk),
                "game_id": str(ticket_game_id or self.game.pk),
            }
        )
        await consumer.connect()
        return consumer, output

    def last_payload(self, output):
        return json.loads(output[-1]["text"])

    def test_connection_sends_a_player_specific_snapshot(self):
        asyncio.run(asyncio.wait_for(self._test_player_specific_snapshot(), 10))

    async def _test_player_specific_snapshot(self):
        fake_redis = FakeRedis()
        with (
            patch("apps.realtime.consumers.Redis.from_url", return_value=fake_redis),
            patch(
                "apps.realtime.consumers.database_sync_to_async",
                new=lambda function: fake_database_sync_to_async(self, function),
            ),
        ):
            host_socket, host_output = await self.make_consumer(self.host)
            guest_socket, guest_output = await self.make_consumer(self.guest)

            host_snapshot = self.last_payload(host_output)
            guest_snapshot = self.last_payload(guest_output)
            self.assertEqual(host_snapshot["type"], "game.snapshot")
            self.assertEqual(len(host_snapshot["state"]["hand"]), 6)
            self.assertEqual(len(guest_snapshot["state"]["hand"]), 6)

            guest_on_host_view = next(
                player
                for player in host_snapshot["state"]["players"]
                if player["player_id"] == str(self.guest_seat.pk)
            )
            host_on_guest_view = next(
                player
                for player in guest_snapshot["state"]["players"]
                if player["player_id"] == str(self.host_seat.pk)
            )
            self.assertNotIn("hand", guest_on_host_view)
            self.assertNotIn("hand", host_on_guest_view)
            self.assertEqual(guest_on_host_view["hand_count"], 6)
            self.assertEqual(host_on_guest_view["hand_count"], 6)
            await host_socket.disconnect(1000)
            await guest_socket.disconnect(1000)

    def test_non_member_and_wrong_room_ticket_are_rejected(self):
        asyncio.run(self._test_connection_authorization())

    async def _test_connection_authorization(self):
        fake_redis = FakeRedis()
        with (
            patch("apps.realtime.consumers.Redis.from_url", return_value=fake_redis),
            patch(
                "apps.realtime.consumers.database_sync_to_async",
                new=lambda function: fake_database_sync_to_async(self, function),
            ),
        ):
            stranger_socket, stranger_output = await self.make_consumer(self.stranger)
            self.assertEqual(stranger_output[-1]["type"], "websocket.close")
            self.assertEqual(stranger_output[-1]["code"], 4403)

            wrong_ticket_socket, wrong_ticket_output = await self.make_consumer(
                self.host,
                ticket_game_id=uuid4(),
            )
            self.assertEqual(wrong_ticket_output[-1]["type"], "websocket.close")
            self.assertEqual(wrong_ticket_output[-1]["code"], 4403)
            self.assertIsNone(wrong_ticket_socket.redis)

    def test_server_rejects_out_of_turn_action_and_persists_valid_draw(self):
        asyncio.run(self._test_action_validation_and_draw())

    async def _test_action_validation_and_draw(self):
        fake_redis = FakeRedis()
        with (
            patch("apps.realtime.consumers.Redis.from_url", return_value=fake_redis),
            patch(
                "apps.realtime.consumers.database_sync_to_async",
                new=lambda function: fake_database_sync_to_async(self, function),
            ),
        ):
            guest_socket, guest_output = await self.make_consumer(self.guest)
            snapshot = self.last_payload(guest_output)
            await guest_socket.receive_json(
                {
                    "type": "game.action",
                    "request_id": str(uuid4()),
                    "state_version": snapshot["game"]["state_version"],
                    "action": "draw",
                }
            )
            self.assertEqual(guest_output[-1]["type"], "websocket.send")
            error = json.loads(guest_output[-1]["text"])
            self.assertEqual(error["type"], "game.error")
            self.assertEqual(error["code"], "not_your_turn")
            await guest_socket.disconnect(1000)

            host_socket, host_output = await self.make_consumer(self.host)
            host_snapshot = self.last_payload(host_output)
            request_id = str(uuid4())
            await host_socket.receive_json(
                {
                    "type": "game.action",
                    "request_id": request_id,
                    "state_version": host_snapshot["game"]["state_version"],
                    "action": "draw",
                }
            )
            acknowledgement = json.loads(host_output[-1]["text"])
            self.assertEqual(acknowledgement["type"], "game.ack")
            self.assertFalse(acknowledgement["duplicate"])

            replay = dict(
                type="game.action",
                request_id=request_id,
                state_version=host_snapshot["game"]["state_version"],
                action="draw",
            )
            await host_socket.receive_json(replay)
            duplicate_ack = json.loads(host_output[-1]["text"])
            self.assertEqual(duplicate_ack["type"], "game.ack")
            self.assertTrue(duplicate_ack["duplicate"])

            # This consumer test fakes the persistence adapter; the authoritative
            # service is covered with real transactions in its own test below.
            await host_socket.disconnect(1000)

    def test_private_event_payload_is_only_delivered_to_its_owner(self):
        asyncio.run(self._test_private_event_projection())

    async def _test_private_event_projection(self):
        fake_redis = FakeRedis()
        with (
            patch("apps.realtime.consumers.Redis.from_url", return_value=fake_redis),
            patch(
                "apps.realtime.consumers.database_sync_to_async",
                new=lambda function: fake_database_sync_to_async(self, function),
            ),
        ):
            host_socket, host_output = await self.make_consumer(self.host)
            guest_socket, guest_output = await self.make_consumer(self.guest)
            host_socket._is_participant = AsyncMock(return_value=True)
            guest_socket._is_participant = AsyncMock(return_value=True)
            host_socket._get_snapshot = AsyncMock(
                return_value=self.snapshots[self.host.pk]
            )
            guest_socket._get_snapshot = AsyncMock(
                return_value=self.snapshots[self.guest.pk]
            )
            group_message = {
                "event": {
                    "id": str(uuid4()),
                    "sequence": 12,
                    "event_type": "game.action",
                    "actor_display_name": self.host.display_name,
                    "public": {"events": [{"event_type": "card.drawn"}]},
                    "private": {
                        str(self.host.pk): {"card_type": "km_25"},
                        str(self.guest.pk): {"card_type": "repairs"},
                    },
                    "created_at": "2026-11-25T12:00:00+00:00",
                }
            }

            await host_socket.lobby_event(group_message)
            await guest_socket.lobby_event(group_message)
            host_message = self.last_payload(host_output)
            guest_message = self.last_payload(guest_output)
            self.assertEqual(
                host_message["event"]["private"], {"card_type": "km_25"}
            )
            self.assertEqual(
                guest_message["event"]["private"], {"card_type": "repairs"}
            )
            await host_socket.disconnect(1000)
            await guest_socket.disconnect(1000)

    def test_authoritative_actions_check_turn_version_and_are_idempotent(self):
        version = self.game.state_version
        request_id = uuid4()
        game, duplicate = apply_multiplayer_action(
            game_id=self.game.pk,
            user=self.host,
            request_id=request_id,
            expected_version=version,
            action="draw",
        )
        self.assertFalse(duplicate)
        self.assertEqual(game.state_version, version + 1)

        game, duplicate = apply_multiplayer_action(
            game_id=self.game.pk,
            user=self.host,
            request_id=request_id,
            expected_version=version,
            action="draw",
        )
        self.assertTrue(duplicate)
        self.assertEqual(game.state_version, version + 1)

        with self.assertRaises(GameActionRejected) as wrong_turn:
            apply_multiplayer_action(
                game_id=self.game.pk,
                user=self.guest,
                request_id=uuid4(),
                expected_version=game.state_version,
                action="draw",
            )
        self.assertEqual(wrong_turn.exception.get_codes(), "not_your_turn")

        with self.assertRaises(GameConflict):
            apply_multiplayer_action(
                game_id=self.game.pk,
                user=self.host,
                request_id=uuid4(),
                expected_version=version,
                action="draw",
            )

    def test_reconnection_snapshot_restores_same_hand(self):
        asyncio.run(self._test_reconnect_state())

    async def _test_reconnect_state(self):
        fake_redis = FakeRedis()
        with (
            patch("apps.realtime.consumers.Redis.from_url", return_value=fake_redis),
            patch(
                "apps.realtime.consumers.database_sync_to_async",
                new=lambda function: fake_database_sync_to_async(self, function),
            ),
        ):
            first_socket, first_output = await self.make_consumer(self.host)
            first_hand = [
                card["id"]
                for card in self.last_payload(first_output)["state"]["hand"]
            ]
            await first_socket.disconnect(1000)

            resumed_socket, resumed_output = await self.make_consumer(self.host)
            resumed_hand = [
                card["id"]
                for card in self.last_payload(resumed_output)["state"]["hand"]
            ]
            self.assertEqual(resumed_hand, first_hand)
            await resumed_socket.disconnect(1000)
