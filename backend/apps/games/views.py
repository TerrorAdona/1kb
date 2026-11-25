from rest_framework import generics, status
from rest_framework.exceptions import NotFound
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from .models import Game
from .permissions import CanViewGame, IsGameHost, IsGameParticipant
from .serializers import GameCreateSerializer, GameReadSerializer, JoinGameSerializer, ReadySerializer
from .services import (
    create_game,
    get_game_for_user,
    join_game,
    leave_game,
    list_available_games,
    list_my_games,
    set_ready,
    start_game,
)


class GameListCreateView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        queryset = list_available_games()
        page = self.paginate_queryset(queryset)
        serializer = GameReadSerializer(
            page if page is not None else queryset, many=True
        )
        if page is not None:
            return self.get_paginated_response(serializer.data)
        return Response(serializer.data)

    def post(self, request):
        serializer = GameCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        game, invite_code = create_game(host=request.user, **serializer.validated_data)
        response_data = GameReadSerializer(game).data
        if invite_code:
            response_data["invite_code"] = invite_code
        return Response(response_data, status=status.HTTP_201_CREATED)


class MyGamesView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        queryset = list_my_games(request.user)
        page = self.paginate_queryset(queryset)
        serializer = GameReadSerializer(
            page if page is not None else queryset, many=True
        )
        if page is not None:
            return self.get_paginated_response(serializer.data)
        return Response(serializer.data)

    def paginate_queryset(self, queryset):
        from rest_framework.pagination import PageNumberPagination

        self._paginator = PageNumberPagination()
        self._paginator.page_size = 20
        return self._paginator.paginate_queryset(queryset, self.request, view=self)

    def get_paginated_response(self, data):
        return self._paginator.get_paginated_response(data)


class GameDetailView(APIView):
    permission_classes = [IsAuthenticated, CanViewGame]

    def get_object(self, game_id):
        try:
            game = (
                Game.objects.select_related("host", "result__winner")
                .prefetch_related("participants")
                .get(pk=game_id)
            )
        except Game.DoesNotExist as exc:
            raise NotFound("Partie introuvable.") from exc
        self.check_object_permissions(self.request, game)
        return game

    def get(self, request, game_id):
        game = self.get_object(game_id)
        return Response(GameReadSerializer(game).data)


class GameJoinView(APIView):
    permission_classes = [IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "game_join"

    def post(self, request, game_id):
        serializer = JoinGameSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        game = join_game(
            game_id=game_id,
            user=request.user,
            invite_code=serializer.validated_data.get("invite_code"),
        )
        game = get_game_for_user(game_id=game.pk, user=request.user)
        return Response(GameReadSerializer(game).data, status=status.HTTP_200_OK)


class GameLeaveView(APIView):
    permission_classes = [IsAuthenticated, IsGameParticipant]

    def post(self, request, game_id):
        game = get_game_for_user(game_id=game_id, user=request.user)
        self.check_object_permissions(request, game)
        game = leave_game(game_id=game_id, user=request.user)
        return Response(GameReadSerializer(game).data)


class GameReadyView(APIView):
    permission_classes = [IsAuthenticated, IsGameParticipant]

    def patch(self, request, game_id):
        serializer = ReadySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        game = get_game_for_user(game_id=game_id, user=request.user)
        self.check_object_permissions(request, game)
        game = set_ready(
            game_id=game_id,
            user=request.user,
            is_ready=serializer.validated_data["is_ready"],
        )
        game = get_game_for_user(game_id=game.pk, user=request.user)
        return Response(GameReadSerializer(game).data)


class GameStartView(APIView):
    permission_classes = [IsAuthenticated, IsGameHost]

    def post(self, request, game_id):
        game = get_game_for_user(game_id=game_id, user=request.user)
        self.check_object_permissions(request, game)
        game = start_game(game_id=game_id, user=request.user)
        game = get_game_for_user(game_id=game.pk, user=request.user)
        return Response(GameReadSerializer(game).data)
