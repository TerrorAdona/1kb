from django.conf import settings
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from apps.games.permissions import IsGameParticipant
from apps.games.services import get_game_for_user

from .tickets import issue_websocket_ticket


class GameWebSocketTicketView(APIView):
    permission_classes = [IsAuthenticated, IsGameParticipant]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "ws_ticket"

    def post(self, request, game_id):
        game = get_game_for_user(game_id=game_id, user=request.user)
        self.check_object_permissions(request, game)
        ticket = issue_websocket_ticket(request.user.pk, game.pk)
        return Response(
            {
                "ticket": ticket,
                "expires_in": settings.JWT_WS_TICKET_TTL_SECONDS,
                "websocket_path": f"/ws/games/{game.pk}/",
            }
        )
