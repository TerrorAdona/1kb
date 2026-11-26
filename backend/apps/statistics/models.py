from django.conf import settings
from django.db import models


class PlayerStats(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="stats",
    )
    games_played = models.PositiveIntegerField(default=0)
    wins = models.PositiveIntegerField(default=0)
    losses = models.PositiveIntegerField(default=0)
    total_kilometers = models.PositiveIntegerField(default=0)
    best_kilometers = models.PositiveSmallIntegerField(default=0)
    solo_games_played = models.PositiveIntegerField(default=0)
    multiplayer_games_played = models.PositiveIntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=models.Q(wins__lte=models.F("games_played")),
                name="statistics_wins_not_over_games",
            )
        ]

    @property
    def win_rate(self) -> float:
        if not self.games_played:
            return 0.0
        return round(self.wins / self.games_played * 100, 1)

    @property
    def average_kilometers(self) -> float:
        if not self.games_played:
            return 0.0
        return round(self.total_kilometers / self.games_played, 1)

    def __str__(self) -> str:
        return f"Stats de {self.user_id}"
