from django.urls import path

from .consumers import GameLobbyConsumer

websocket_urlpatterns = [
    path("ws/games/<uuid:game_id>/lobby/", GameLobbyConsumer.as_asgi()),
]
