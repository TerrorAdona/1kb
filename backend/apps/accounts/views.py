import json
import logging

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import update_last_login
from django.http import HttpResponse, JsonResponse
from django.middleware.csrf import get_token
from django.views.decorators.csrf import csrf_protect, ensure_csrf_cookie
from django.views.decorators.http import require_GET, require_POST
from rest_framework import generics, status
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.serializers import TokenRefreshSerializer
from rest_framework_simplejwt.tokens import RefreshToken

from .serializers import LoginSerializer, ProfileUpdateSerializer, RegistrationSerializer, UserSerializer
from .throttles import LoginRateThrottle

logger = logging.getLogger(__name__)
User = get_user_model()


def _json_body(request):
    if not request.body:
        return {}
    try:
        payload = json.loads(request.body)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def _set_refresh_cookie(response, token: str) -> None:
    lifetime = settings.SIMPLE_JWT["REFRESH_TOKEN_LIFETIME"]
    response.set_cookie(
        settings.JWT_REFRESH_COOKIE_NAME,
        str(token),
        max_age=int(lifetime.total_seconds()),
        httponly=True,
        secure=settings.JWT_REFRESH_COOKIE_SECURE,
        samesite=settings.JWT_REFRESH_COOKIE_SAMESITE,
        domain=settings.JWT_REFRESH_COOKIE_DOMAIN,
        path=settings.JWT_REFRESH_COOKIE_PATH,
    )


def _clear_refresh_cookie(response) -> None:
    response.delete_cookie(
        settings.JWT_REFRESH_COOKIE_NAME,
        path=settings.JWT_REFRESH_COOKIE_PATH,
        domain=settings.JWT_REFRESH_COOKIE_DOMAIN,
        samesite=settings.JWT_REFRESH_COOKIE_SAMESITE,
    )


class RegistrationView(generics.CreateAPIView):
    queryset = User.objects.all()
    serializer_class = RegistrationSerializer
    permission_classes = [AllowAny]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        return Response(UserSerializer(user).data, status=status.HTTP_201_CREATED)


class ProfileView(generics.RetrieveUpdateAPIView):
    permission_classes = [IsAuthenticated]

    def get_object(self):
        return self.request.user

    def get_serializer_class(self):
        if self.request.method in {"PUT", "PATCH"}:
            return ProfileUpdateSerializer
        return UserSerializer

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        return Response(UserSerializer(instance).data)


@ensure_csrf_cookie
@require_GET
def csrf_cookie_view(request):
    return JsonResponse({"csrfToken": get_token(request)})


@csrf_protect
@require_POST
def login_view(request):
    throttle = LoginRateThrottle()
    if not throttle.allow_request(request, view=None):
        return JsonResponse(
            {"detail": "Trop de tentatives. Réessayez dans quelques instants."},
            status=429,
        )
    payload = _json_body(request)
    if payload is None:
        return JsonResponse({"detail": "Corps JSON invalide."}, status=400)
    serializer = LoginSerializer(data=payload, context={"request": request})
    try:
        serializer.is_valid(raise_exception=True)
    except ValidationError as exc:
        return JsonResponse(exc.detail, status=400)

    user = serializer.validated_data["user"]
    update_last_login(None, user)
    refresh = RefreshToken.for_user(user)
    response = JsonResponse(
        {"access": str(refresh.access_token), "user": UserSerializer(user).data}
    )
    _set_refresh_cookie(response, str(refresh))
    return response


@csrf_protect
@require_POST
def refresh_view(request):
    raw_refresh = request.COOKIES.get(settings.JWT_REFRESH_COOKIE_NAME)
    if not raw_refresh:
        return JsonResponse({"detail": "Session de renouvellement absente."}, status=401)

    try:
        refresh_token = RefreshToken(raw_refresh)
        User.objects.get(pk=refresh_token["user_id"], is_active=True)
    except (TokenError, User.DoesNotExist, KeyError, ValueError):
        logger.info("Refus d’un jeton de renouvellement invalide ou expiré.")
        response = JsonResponse(
            {"detail": "Session expirée. Veuillez vous reconnecter."}, status=401
        )
        _clear_refresh_cookie(response)
        return response

    serializer = TokenRefreshSerializer(data={"refresh": raw_refresh})
    try:
        serializer.is_valid(raise_exception=True)
    except (ValidationError, TokenError):
        logger.info("Refus d’un jeton de renouvellement invalide ou expiré.")
        response = JsonResponse(
            {"detail": "Session expirée. Veuillez vous reconnecter."}, status=401
        )
        _clear_refresh_cookie(response)
        return response

    tokens = serializer.validated_data
    response = JsonResponse({"access": tokens["access"]})
    _set_refresh_cookie(response, tokens.get("refresh", raw_refresh))
    return response


@csrf_protect
@require_POST
def logout_view(request):
    raw_refresh = request.COOKIES.get(settings.JWT_REFRESH_COOKIE_NAME)
    if raw_refresh:
        try:
            RefreshToken(raw_refresh).blacklist()
        except TokenError:
            # La déconnexion reste idempotente même si le cookie est expiré/invalide.
            pass
    response = HttpResponse(status=204)
    _clear_refresh_cookie(response)
    return response
