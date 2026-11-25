from django.contrib import admin

from .models import PlayerStats


@admin.register(PlayerStats)
class PlayerStatsAdmin(admin.ModelAdmin):
    list_display = ["user", "games_played", "wins", "total_kilometers", "best_kilometers"]
    search_fields = ["user__email", "user__display_name"]
    readonly_fields = [
        "user",
        "games_played",
        "wins",
        "total_kilometers",
        "best_kilometers",
        "updated_at",
    ]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
