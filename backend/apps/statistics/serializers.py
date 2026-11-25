from rest_framework import serializers

from apps.games.models import Game, GameParticipant
from .models import PlayerStats


class HistoryParticipantSerializer(serializers.ModelSerializer):
    class Meta:
        model = GameParticipant
        fields = ["display_name", "kind", "seat_number", "kilometers", "placement"]
        read_only_fields = fields


class GameHistorySerializer(serializers.ModelSerializer):
    participants = HistoryParticipantSerializer(many=True, read_only=True)
    winner_display_name = serializers.CharField(
        source="result.winner.display_name", read_only=True
    )
    completed_at = serializers.DateTimeField(source="result.completed_at", read_only=True)

    class Meta:
        model = Game
        fields = [
            "id",
            "mode",
            "ruleset_version",
            "participants",
            "winner_display_name",
            "completed_at",
        ]


class PlayerStatsSerializer(serializers.ModelSerializer):
    win_rate = serializers.SerializerMethodField()

    class Meta:
        model = PlayerStats
        fields = [
            "games_played",
            "wins",
            "win_rate",
            "total_kilometers",
            "best_kilometers",
            "updated_at",
        ]
        read_only_fields = fields

    def get_win_rate(self, obj):
        if not obj.games_played:
            return 0
        return round(obj.wins / obj.games_played * 100, 1)
