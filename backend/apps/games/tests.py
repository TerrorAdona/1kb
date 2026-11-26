from django.test import TestCase, override_settings
from rest_framework.test import APIClient
from uuid import uuid4

from apps.accounts.models import User
from apps.statistics.models import PlayerStats
from .models import Game, GameParticipant, GameResult
from .services import apply_solo_action, finish_game


@override_settings(
    CACHES={
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "games-tests",
        }
    },
    CHANNEL_LAYERS={
        "default": {"BACKEND": "channels.layers.InMemoryChannelLayer"}
    },
)
class GameLobbyApiTests(TestCase):
    def setUp(self):
        self.host = User.objects.create_user(
            "host@example.com", "Valid-password-481!Card", display_name="Host"
        )
        self.guest = User.objects.create_user(
            "guest@example.com", "Valid-password-481!Card", display_name="Guest"
        )
        self.other = User.objects.create_user(
            "other@example.com", "Valid-password-481!Card", display_name="Other"
        )
        self.client = APIClient()

    def authenticate(self, user):
        self.client.force_authenticate(user=user)

    def create_game(self, **overrides):
        payload = {
            "mode": "multiplayer",
            "visibility": "private",
            "max_players": 4,
        }
        payload.update(overrides)
        self.authenticate(self.host)
        return self.client.post("/api/v1/games/", payload, format="json")

    def test_private_game_requires_the_invitation_code(self):
        created = self.create_game()
        self.assertEqual(created.status_code, 201)
        invite_code = created.data["invite_code"]
        game_id = created.data["id"]
        self.assertNotIn("invite_code_hash", created.data)

        self.authenticate(self.guest)
        wrong = self.client.post(
            f"/api/v1/games/{game_id}/join/",
            {"invite_code": "wrong-code"},
            format="json",
        )
        self.assertEqual(wrong.status_code, 403)
        self.assertEqual(GameParticipant.objects.filter(game_id=game_id).count(), 1)
        hidden = self.client.get(f"/api/v1/games/{game_id}/")
        self.assertEqual(hidden.status_code, 403)

        joined = self.client.post(
            f"/api/v1/games/{game_id}/join/",
            {"invite_code": invite_code},
            format="json",
        )
        self.assertEqual(joined.status_code, 200)
        self.assertEqual(joined.data["seats_taken"], 2)

    def test_available_list_excludes_private_games(self):
        self.assertEqual(self.create_game().status_code, 201)
        self.authenticate(self.other)
        response = self.client.get("/api/v1/games/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 0)

    def test_public_game_capacity_and_ready_start_permissions(self):
        created = self.create_game(visibility="public", max_players=2)
        self.assertEqual(created.status_code, 201)
        self.assertNotIn("invite_code", created.data)
        game_id = created.data["id"]

        self.authenticate(self.guest)
        joined = self.client.post(
            f"/api/v1/games/{game_id}/join/", {}, format="json"
        )
        self.assertEqual(joined.status_code, 200)
        guest_ready = self.client.patch(
            f"/api/v1/games/{game_id}/ready/",
            {"is_ready": True},
            format="json",
        )
        self.assertEqual(guest_ready.status_code, 200)

        self.authenticate(self.other)
        full = self.client.post(
            f"/api/v1/games/{game_id}/join/", {}, format="json"
        )
        self.assertEqual(full.status_code, 409)

        self.authenticate(self.host)
        host_ready = self.client.patch(
            f"/api/v1/games/{game_id}/ready/",
            {"is_ready": True},
            format="json",
        )
        self.assertEqual(host_ready.status_code, 200)

        started = self.client.post(f"/api/v1/games/{game_id}/start/")
        self.assertEqual(started.status_code, 200)
        self.assertEqual(started.data["status"], Game.Status.ACTIVE)

        self.authenticate(self.guest)
        cannot_start = self.client.post(f"/api/v1/games/{game_id}/start/")
        self.assertEqual(cannot_start.status_code, 403)

    def test_host_leaving_transfers_ownership(self):
        created = self.create_game()
        game_id = created.data["id"]
        self.authenticate(self.guest)
        self.client.post(
            f"/api/v1/games/{game_id}/join/",
            {"invite_code": created.data["invite_code"]},
            format="json",
        )
        self.authenticate(self.host)
        response = self.client.post(f"/api/v1/games/{game_id}/leave/")
        self.assertEqual(response.status_code, 200)
        game = Game.objects.get(pk=game_id)
        self.assertEqual(game.host_id, self.guest.id)
        self.assertFalse(
            GameParticipant.objects.filter(game=game, user=self.host).exists()
        )

    def test_solo_game_fills_remaining_seats_with_bots_at_selected_difficulty(self):
        created = self.create_game(
            mode="solo",
            visibility="private",
            max_players=3,
            bot_difficulty="hard",
        )
        self.assertEqual(created.status_code, 201)
        self.assertEqual(created.data["seats_taken"], 3)
        bots = GameParticipant.objects.filter(
            game_id=created.data["id"], kind=GameParticipant.Kind.BOT
        )
        self.assertEqual(bots.count(), 2)
        self.assertEqual(set(bots.values_list("bot_difficulty", flat=True)), {"hard"})

    def test_starting_solo_game_initializes_the_shared_engine_state(self):
        created = self.create_game(
            mode="solo",
            visibility="private",
            max_players=3,
            bot_difficulty="normal",
        )
        game_id = created.data["id"]
        started = self.client.post(f"/api/v1/games/{game_id}/start/")
        self.assertEqual(started.status_code, 200)

        game = Game.objects.get(pk=game_id)
        self.assertEqual(game.status, Game.Status.ACTIVE)
        self.assertEqual(game.state["phase"], "draw")
        self.assertEqual(len(game.state["players"]), 3)
        self.assertTrue(
            all(len(player["hand"]) == 6 for player in game.state["players"])
        )
        bot_ids = {
            str(participant.pk)
            for participant in GameParticipant.objects.filter(
                game=game, kind=GameParticipant.Kind.BOT
            )
        }
        self.assertTrue(
            bot_ids.issubset(
                {player["player_id"] for player in game.state["players"]}
            )
        )

    def test_finish_game_records_result_distance_and_stats(self):
        created = self.create_game(visibility="public", max_players=2)
        game_id = created.data["id"]
        self.authenticate(self.guest)
        self.client.post(f"/api/v1/games/{game_id}/join/", {}, format="json")
        self.client.patch(
            f"/api/v1/games/{game_id}/ready/",
            {"is_ready": True},
            format="json",
        )
        self.authenticate(self.host)
        self.client.patch(
            f"/api/v1/games/{game_id}/ready/",
            {"is_ready": True},
            format="json",
        )
        self.client.post(f"/api/v1/games/{game_id}/start/")

        participants = {
            participant.user_id: participant
            for participant in GameParticipant.objects.filter(game_id=game_id)
        }
        winner = participants[self.host.pk]
        finish_game(
            game_id=game_id,
            winner_participant_id=winner.pk,
            kilometers_by_participant={
                str(participants[self.host.pk].pk): 700,
                str(participants[self.guest.pk].pk): 450,
            },
        )

        game = Game.objects.get(pk=game_id)
        self.assertEqual(game.status, Game.Status.FINISHED)
        self.assertEqual(GameResult.objects.get(game=game).winner_id, winner.pk)
        self.assertEqual(
            GameParticipant.objects.get(pk=winner.pk).kilometers,
            700,
        )
        host_stats = PlayerStats.objects.get(user=self.host)
        guest_stats = PlayerStats.objects.get(user=self.guest)
        self.assertEqual((host_stats.games_played, host_stats.wins), (1, 1))
        self.assertEqual(host_stats.total_kilometers, 700)
        self.assertEqual((guest_stats.games_played, guest_stats.wins), (1, 0))
        history = self.client.get("/api/v1/history/")
        self.assertEqual(history.status_code, 200)
        self.assertEqual(history.data["count"], 1)
        stats = self.client.get("/api/v1/stats/me/")
        self.assertEqual(stats.status_code, 200)
        self.assertEqual(stats.data["win_rate"], 100.0)


@override_settings(
    CACHES={
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "solo-tests",
        }
    },
    REST_FRAMEWORK={
        "DEFAULT_THROTTLE_CLASSES": [],
        "DEFAULT_THROTTLE_RATES": {
            "game_action": "1000/minute",
            "game_join": "1000/minute",
            "ws_ticket": "1000/minute",
            "auth_login": "1000/minute",
        },
    },
)
class SoloGameIntegrationTests(TestCase):
    """Integration tests for solo game mode with AI opponents."""

    def setUp(self):
        self.user = User.objects.create_user(
            "solo@example.com", "Valid-password-481!Card", display_name="SoloPlayer"
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def create_and_start_solo(self, max_players=3, difficulty="normal"):
        created = self.client.post(
            "/api/v1/games/",
            {
                "mode": "solo",
                "visibility": "private",
                "max_players": max_players,
                "bot_difficulty": difficulty,
            },
            format="json",
        )
        self.assertEqual(created.status_code, 201)
        game_id = created.data["id"]
        started = self.client.post(f"/api/v1/games/{game_id}/start/", format="json")
        self.assertEqual(started.status_code, 200)
        return game_id

    def test_solo_game_creation_and_start(self):
        game_id = self.create_and_start_solo(max_players=3, difficulty="easy")
        game = Game.objects.get(pk=game_id)

        self.assertEqual(game.status, Game.Status.ACTIVE)
        self.assertEqual(game.mode, Game.Mode.SOLO)
        self.assertEqual(game.state["phase"], "draw")
        participants = GameParticipant.objects.filter(game=game)
        self.assertEqual(participants.count(), 3)
        human_count = participants.filter(kind=GameParticipant.Kind.HUMAN).count()
        bot_count = participants.filter(kind=GameParticipant.Kind.BOT).count()
        self.assertEqual(human_count, 1)
        self.assertEqual(bot_count, 2)
        bots = participants.filter(kind=GameParticipant.Kind.BOT)
        for bot in bots:
            self.assertEqual(bot.bot_difficulty, "easy")

    def test_solo_action_draw_card(self):
        game_id = self.create_and_start_solo(max_players=2)
        game = Game.objects.get(pk=game_id)
        human = GameParticipant.objects.get(game=game, kind=GameParticipant.Kind.HUMAN)
        initial_version = game.state_version

        response = self.client.post(
            f"/api/v1/games/{game_id}/action/",
            {
                "action": "draw",
                "state_version": initial_version,
                "request_id": str(uuid4()),
            },
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["state_version"], initial_version + 1)
        self.assertFalse(response.data["duplicate"])

        game.refresh_from_db()
        self.assertEqual(game.state["phase"], "action")
        human.refresh_from_db()
        self.assertEqual(len(game.state["players"][0]["hand"]), 7)

    def test_solo_action_play_distance_card(self):
        game_id = self.create_and_start_solo(max_players=2)
        game = Game.objects.get(pk=game_id)
        human = GameParticipant.objects.get(game=game, kind=GameParticipant.Kind.HUMAN)

        # Draw first
        draw_resp = self.client.post(
            f"/api/v1/games/{game_id}/action/",
            {
                "action": "draw",
                "state_version": game.state_version,
                "request_id": str(uuid4()),
            },
            format="json",
        )
        self.assertEqual(draw_resp.status_code, 200)
        game.refresh_from_db()

        # Find a distance card in hand
        hand = game.state["players"][0]["hand"]
        distance_card = next(
            (card for card in hand if card["card_type"].startswith("km_")), None
        )
        self.assertIsNotNone(distance_card)

        # Play the distance card
        play_resp = self.client.post(
            f"/api/v1/games/{game_id}/action/",
            {
                "action": "play",
                "card_id": distance_card["id"],
                "state_version": game.state_version,
                "request_id": str(uuid4()),
            },
            format="json",
        )
        self.assertEqual(play_resp.status_code, 200)

        game.refresh_from_db()
        # After playing distance, turn completes and bots play until human's turn
        # Game should be in DRAW phase for human again, RESPONSE if bot attacked,
        # or FINISHED
        self.assertIn(game.state["phase"], ["draw", "response", "finished"])

    def test_solo_action_idempotency(self):
        game_id = self.create_and_start_solo(max_players=2)
        game = Game.objects.get(pk=game_id)
        request_id = str(uuid4())

        # First draw
        resp1 = self.client.post(
            f"/api/v1/games/{game_id}/action/",
            {
                "action": "draw",
                "state_version": game.state_version,
                "request_id": request_id,
            },
            format="json",
        )
        self.assertEqual(resp1.status_code, 200)
        self.assertFalse(resp1.data["duplicate"])
        game.refresh_from_db()

        # Duplicate draw with same request_id
        resp2 = self.client.post(
            f"/api/v1/games/{game_id}/action/",
            {
                "action": "draw",
                "state_version": resp1.data["state_version"],  # old version
                "request_id": request_id,
            },
            format="json",
        )
        self.assertEqual(resp2.status_code, 200)
        self.assertTrue(resp2.data["duplicate"])
        game.refresh_from_db()
        # State version should not have changed
        self.assertEqual(game.state_version, resp1.data["state_version"])

    def test_solo_action_invalid_version_rejected(self):
        game_id = self.create_and_start_solo(max_players=2)

        response = self.client.post(
            f"/api/v1/games/{game_id}/action/",
            {
                "action": "draw",
                "state_version": 999,  # Wrong version
                "request_id": str(uuid4()),
            },
            format="json",
        )
        self.assertEqual(response.status_code, 409)

    def test_solo_action_not_allowed_in_multiplayer(self):
        # Create multiplayer game
        created = self.client.post(
            "/api/v1/games/",
            {
                "mode": "multiplayer",
                "visibility": "public",
                "max_players": 2,
            },
            format="json",
        )
        self.assertEqual(created.status_code, 201)
        game_id = created.data["id"]

        # Try to use solo action endpoint
        response = self.client.post(
            f"/api/v1/games/{game_id}/action/",
            {
                "action": "draw",
                "state_version": 0,
                "request_id": str(uuid4()),
            },
            format="json",
        )
        self.assertEqual(response.status_code, 400)

    def test_solo_game_flow_draw_play_bots_respond(self):
        """Test a complete turn: human draws, plays, bots play automatically."""
        game_id = self.create_and_start_solo(max_players=3)  # 2 bots
        game = Game.objects.get(pk=game_id)

        # Human draws
        resp = self.client.post(
            f"/api/v1/games/{game_id}/action/",
            {
                "action": "draw",
                "state_version": game.state_version,
                "request_id": str(uuid4()),
            },
            format="json",
        )
        self.assertEqual(resp.status_code, 200)
        game.refresh_from_db()
        self.assertEqual(game.state["phase"], "action")

        # Human plays a distance card if available
        hand = game.state["players"][0]["hand"]
        distance_card = next(
            (card for card in hand if card["card_type"].startswith("km_")), None
        )
        if distance_card:
            resp = self.client.post(
                f"/api/v1/games/{game_id}/action/",
                {
                    "action": "play",
                    "card_id": distance_card["id"],
                    "state_version": game.state_version,
                    "request_id": str(uuid4()),
                },
                format="json",
            )
            self.assertEqual(resp.status_code, 200)
            game.refresh_from_db()

            # After human plays, bots should have played and it should be human's turn again
            # (DRAW phase), RESPONSE if bot attacked human, or game finished
            self.assertIn(game.state["phase"], ["draw", "response", "finished"])

            # Human participant should be the active player if game continues and it's draw phase
            if game.state["phase"] == "draw":
                active_id = game.state["players"][game.state["active_player_index"]]["player_id"]
                self.assertEqual(active_id, str(game.participants.get(kind=GameParticipant.Kind.HUMAN).pk))

    def test_solo_game_finishes_and_records_stats(self):
        """Test that a finished solo game records result and stats."""
        game_id = self.create_and_start_solo(max_players=2)
        game = Game.objects.get(pk=game_id)
        human = GameParticipant.objects.get(game=game, kind=GameParticipant.Kind.HUMAN)
        bot = GameParticipant.objects.get(game=game, kind=GameParticipant.Kind.BOT)

        # Finish the game manually via service
        from .services import finish_game

        finish_game(
            game_id=game_id,
            winner_participant_id=human.pk,
            kilometers_by_participant={
                str(human.pk): 1000,
                str(bot.pk): 300,
            },
        )

        game.refresh_from_db()
        self.assertEqual(game.status, Game.Status.FINISHED)
        result = GameResult.objects.get(game=game)
        self.assertEqual(result.winner_id, human.pk)

        human.refresh_from_db()
        bot.refresh_from_db()
        self.assertEqual(human.kilometers, 1000)
        self.assertEqual(bot.kilometers, 300)

        stats = PlayerStats.objects.get(user=self.user)
        self.assertEqual(stats.games_played, 1)
        self.assertEqual(stats.wins, 1)
        self.assertEqual(stats.total_kilometers, 1000)
