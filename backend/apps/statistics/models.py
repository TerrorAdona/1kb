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
    total_kilometers = models.PositiveIntegerField(default=0)
    best_kilometers = models.PositiveSmallIntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=models.Q(wins__lte=models.F("games_played")),
                name="statistics_wins_not_over_games",
            )
        ]

    def __str__(self) -> str:
        return f"Stats de {self.user_id}"
