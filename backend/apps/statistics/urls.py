from django.urls import path

from .views import GameHistoryView, MyStatsView

urlpatterns = [
    path("history/", GameHistoryView.as_view(), name="game-history"),
    path("stats/me/", MyStatsView.as_view(), name="my-stats"),
]
