import uuid

from django.conf import settings
from django.db import models
from django.db.models import Q
from django.utils import timezone


class Game(models.Model):
    class Mode(models.TextChoices):
        SOLO = "solo", "Solo"
        MULTIPLAYER = "multiplayer", "Multijoueur"

    class Visibility(models.TextChoices):
        PUBLIC = "public", "Publique"
        PRIVATE = "private", "Privée"

    class Status(models.TextChoices):
        WAITING = "waiting", "En attente"
        ACTIVE = "active", "En cours"
        FINISHED = "finished", "Terminée"
        CANCELLED = "cancelled", "Annulée"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    host = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="hosted_games",
    )
    mode = models.CharField(max_length=16, choices=Mode.choices)
    visibility = models.CharField(
        max_length=8, choices=Visibility.choices, default=Visibility.PRIVATE
    )
    status = models.CharField(
        max_length=12, choices=Status.choices, default=Status.WAITING
    )
    max_players = models.PositiveSmallIntegerField(default=4)
    invite_code_hash = models.CharField(max_length=64, null=True, blank=True, unique=True)
    invite_expires_at = models.DateTimeField(null=True, blank=True)
    ruleset_version = models.CharField(max_length=32, default="mille-bornes-v1")
    state_version = models.PositiveIntegerField(default=0)
    state = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.CheckConstraint(
                condition=Q(max_players__gte=2) & Q(max_players__lte=4),
                name="games_player_capacity_2_to_4",
            ),
            models.CheckConstraint(
                condition=Q(visibility="private") | Q(mode="multiplayer"),
                name="solo_games_are_private",
            ),
        ]
        indexes = [
            models.Index(
                fields=["status", "visibility", "created_at"],
                name="games_lobby_listing_idx",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.mode}:{self.id}"


class GameParticipant(models.Model):
    class Kind(models.TextChoices):
        HUMAN = "human", "Humain"
        BOT = "bot", "Bot"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    game = models.ForeignKey(Game, on_delete=models.CASCADE, related_name="participants")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="game_participations",
        null=True,
        blank=True,
    )
    kind = models.CharField(max_length=8, choices=Kind.choices, default=Kind.HUMAN)
    seat_number = models.PositiveSmallIntegerField()
    display_name = models.CharField(max_length=40)
    bot_difficulty = models.CharField(max_length=12, blank=True)
    is_ready = models.BooleanField(default=False)
    kilometers = models.PositiveSmallIntegerField(default=0)
    placement = models.PositiveSmallIntegerField(null=True, blank=True)
    abandoned_at = models.DateTimeField(null=True, blank=True)
    joined_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["seat_number"]
        constraints = [
            models.UniqueConstraint(
                fields=["game", "seat_number"], name="games_unique_seat_per_game"
            ),
            models.UniqueConstraint(
                fields=["game", "user"],
                condition=Q(user__isnull=False),
                name="games_unique_user_per_game",
            ),
            models.CheckConstraint(
                condition=(
                    Q(kind="human", user__isnull=False)
                    | Q(kind="bot", user__isnull=True)
                ),
                name="games_participant_kind_user_consistent",
            ),
            models.CheckConstraint(
                condition=Q(seat_number__gte=1) & Q(seat_number__lte=4),
                name="games_seat_number_1_to_4",
            ),
        ]
        indexes = [models.Index(fields=["user", "joined_at"], name="games_user_joined_idx")]

    def __str__(self) -> str:
        return f"{self.display_name} (siège {self.seat_number})"


class GameEvent(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    game = models.ForeignKey(Game, on_delete=models.CASCADE, related_name="events")
    sequence = models.PositiveIntegerField()
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="game_events",
        null=True,
        blank=True,
    )
    actor_display_name = models.CharField(max_length=40, blank=True)
    request_id = models.UUIDField(null=True, blank=True)
    event_type = models.CharField(max_length=40)
    public_payload = models.JSONField(default=dict, blank=True)
    private_payloads = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["sequence"]
        constraints = [
            models.UniqueConstraint(
                fields=["game", "sequence"], name="games_unique_event_sequence"
            ),
            models.UniqueConstraint(
                fields=["game", "actor", "request_id"],
                condition=Q(request_id__isnull=False),
                name="games_unique_request_per_actor",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.game_id}#{self.sequence} {self.event_type}"


class GameResult(models.Model):
    game = models.OneToOneField(Game, on_delete=models.CASCADE, related_name="result")
    winner = models.ForeignKey(
        GameParticipant,
        on_delete=models.PROTECT,
        related_name="won_results",
    )
    completed_at = models.DateTimeField(default=timezone.now)

    def __str__(self) -> str:
        return f"Résultat de {self.game_id}"
