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
    average_kilometers = serializers.SerializerMethodField()

    class Meta:
        model = PlayerStats
        fields = [
            "games_played",
            "wins",
            "losses",
            "win_rate",
            "total_kilometers",
            "best_kilometers",
            "solo_games_played",
            "multiplayer_games_played",
            "average_kilometers",
            "updated_at",
        ]
        read_only_fields = fields

    def get_win_rate(self, obj):
        if not obj.games_played:
            return 0
        return round(obj.wins / obj.games_played * 100, 1)

    def get_average_kilometers(self, obj):
        if not obj.games_played:
            return 0
        return round(obj.total_kilometers / obj.games_played, 1)


class LeaderboardEntrySerializer(serializers.Serializer):
    rank = serializers.IntegerField()
    user_id = serializers.IntegerField()
    display_name = serializers.CharField()
    games_played = serializers.IntegerField()
    wins = serializers.IntegerField()
    win_rate = serializers.FloatField()
    total_kilometers = serializers.IntegerField()
    best_kilometers = serializers.IntegerField()
    solo_games_played = serializers.IntegerField()
    multiplayer_games_played = serializers.IntegerField()
