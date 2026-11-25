from django.db.models import Prefetch
from rest_framework import generics
from rest_framework.permissions import IsAuthenticated

from apps.games.models import Game, GameParticipant

from .models import PlayerStats
from .serializers import GameHistorySerializer, PlayerStatsSerializer


class GameHistoryView(generics.ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = GameHistorySerializer

    def get_queryset(self):
        return (
            Game.objects.filter(
                status=Game.Status.FINISHED,
                participants__user=self.request.user,
            )
            .select_related("result", "result__winner")
            .prefetch_related(
                Prefetch(
                    "participants",
                    queryset=GameParticipant.objects.order_by("seat_number"),
                )
            )
            .distinct()
        )


class MyStatsView(generics.RetrieveAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = PlayerStatsSerializer

    def get_object(self):
        stats, _ = PlayerStats.objects.get_or_create(user=self.request.user)
        return stats
