from django.urls import path

from apps.realtime.views import GameWebSocketTicketView

from .views import (
    GameDetailView,
    GameJoinView,
    GameLeaveView,
    GameListCreateView,
    GameReadyView,
    GameStartView,
    MyGamesView,
)

urlpatterns = [
    path("games/", GameListCreateView.as_view(), name="game-list-create"),
    path("games/mine/", MyGamesView.as_view(), name="my-games"),
    path("games/<uuid:game_id>/", GameDetailView.as_view(), name="game-detail"),
    path("games/<uuid:game_id>/join/", GameJoinView.as_view(), name="game-join"),
    path("games/<uuid:game_id>/leave/", GameLeaveView.as_view(), name="game-leave"),
    path("games/<uuid:game_id>/ready/", GameReadyView.as_view(), name="game-ready"),
    path("games/<uuid:game_id>/start/", GameStartView.as_view(), name="game-start"),
    path(
        "games/<uuid:game_id>/ws-ticket/",
        GameWebSocketTicketView.as_view(),
        name="game-ws-ticket",
    ),
]
