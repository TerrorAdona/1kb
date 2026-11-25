from rest_framework import serializers

from .models import Game, GameParticipant


class GameParticipantSerializer(serializers.ModelSerializer):
    class Meta:
        model = GameParticipant
        fields = [
            "id",
            "seat_number",
            "kind",
            "display_name",
            "bot_difficulty",
            "is_ready",
            "kilometers",
            "placement",
            "abandoned_at",
            "joined_at",
        ]
        read_only_fields = fields


class GameReadSerializer(serializers.ModelSerializer):
    host_display_name = serializers.CharField(source="host.display_name", read_only=True)
    participants = GameParticipantSerializer(many=True, read_only=True)
    seats_taken = serializers.SerializerMethodField()
    available_seats = serializers.SerializerMethodField()
    winner_display_name = serializers.SerializerMethodField()

    class Meta:
        model = Game
        fields = [
            "id",
            "mode",
            "visibility",
            "status",
            "host_display_name",
            "max_players",
            "seats_taken",
            "available_seats",
            "participants",
            "winner_display_name",
            "ruleset_version",
            "state_version",
            "created_at",
            "updated_at",
            "started_at",
            "finished_at",
        ]
        read_only_fields = fields

    def get_seats_taken(self, obj):
        return len(obj.participants.all())

    def get_available_seats(self, obj):
        return max(0, obj.max_players - self.get_seats_taken(obj))

    def get_winner_display_name(self, obj):
        result = getattr(obj, "result", None)
        return result.winner.display_name if result else None


class GameCreateSerializer(serializers.Serializer):
    mode = serializers.ChoiceField(choices=Game.Mode.choices, default=Game.Mode.MULTIPLAYER)
    visibility = serializers.ChoiceField(
        choices=Game.Visibility.choices, default=Game.Visibility.PRIVATE
    )
    max_players = serializers.IntegerField(min_value=2, max_value=4, default=4)
    bot_difficulty = serializers.ChoiceField(
        choices=[("easy", "Facile"), ("normal", "Normale"), ("hard", "Difficile")],
        default="normal",
    )
    invite_expires_in_hours = serializers.IntegerField(
        min_value=1, max_value=168, required=False, default=24
    )

    def validate(self, attrs):
        if attrs["mode"] == Game.Mode.SOLO and attrs["visibility"] != Game.Visibility.PRIVATE:
            raise serializers.ValidationError(
                {"visibility": "Une partie solo ne peut pas être publique."}
            )
        return attrs


class JoinGameSerializer(serializers.Serializer):
    invite_code = serializers.CharField(
        required=False, allow_blank=False, max_length=32, trim_whitespace=True
    )


class ReadySerializer(serializers.Serializer):
    is_ready = serializers.BooleanField()
