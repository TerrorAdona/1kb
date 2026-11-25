from django.contrib import admin

from .models import Game, GameEvent, GameParticipant, GameResult


class GameParticipantInline(admin.TabularInline):
    model = GameParticipant
    extra = 0
    readonly_fields = ["id", "joined_at", "kilometers", "placement"]


@admin.register(Game)
class GameAdmin(admin.ModelAdmin):
    list_display = ["id", "mode", "visibility", "status", "host", "created_at"]
    list_filter = ["mode", "visibility", "status"]
    search_fields = ["id", "host__email", "host__display_name"]
    readonly_fields = ["id", "invite_code_hash", "state", "state_version", "created_at", "updated_at"]
    inlines = [GameParticipantInline]


@admin.register(GameEvent)
class GameEventAdmin(admin.ModelAdmin):
    list_display = ["game", "sequence", "event_type", "actor_display_name", "created_at"]
    readonly_fields = [
        "id",
        "game",
        "sequence",
        "actor",
        "actor_display_name",
        "request_id",
        "event_type",
        "public_payload",
        "private_payloads",
        "created_at",
    ]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(GameResult)
class GameResultAdmin(admin.ModelAdmin):
    list_display = ["game", "winner", "completed_at"]
    readonly_fields = ["game", "winner", "completed_at"]
