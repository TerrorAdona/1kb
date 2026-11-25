from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.statistics.models import PlayerStats
from .models import Game, GameParticipant, GameResult
from .services import finish_game


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
