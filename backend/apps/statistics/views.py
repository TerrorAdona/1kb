from django.db.models import F, Prefetch
from rest_framework import generics
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.games.models import Game, GameParticipant

from .models import PlayerStats
from .serializers import GameHistorySerializer, LeaderboardEntrySerializer, PlayerStatsSerializer


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


class LeaderboardView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        limit = min(int(request.query_params.get("limit", 50)), 100)
        stats = (
            PlayerStats.objects.filter(games_played__gt=0)
            .select_related("user")
            .order_by("-wins", "-total_kilometers", "-best_kilometers")
            [:limit]
        )

        leaderboard = []
        for rank, stat in enumerate(stats, start=1):
            leaderboard.append(
                {
                    "rank": rank,
                    "user_id": stat.user.id,
                    "display_name": stat.user.display_name,
                    "games_played": stat.games_played,
                    "wins": stat.wins,
                    "win_rate": stat.win_rate,
                    "total_kilometers": stat.total_kilometers,
                    "best_kilometers": stat.best_kilometers,
                    "solo_games_played": stat.solo_games_played,
                    "multiplayer_games_played": stat.multiplayer_games_played,
                }
            )

        serializer = LeaderboardEntrySerializer(leaderboard, many=True)
        return Response(serializer.data)
