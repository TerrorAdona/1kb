import secrets
import json

from django.conf import settings
from django_redis import get_redis_connection


def issue_websocket_ticket(user_id: int, game_id) -> str:
    ticket = secrets.token_urlsafe(32)
    redis = get_redis_connection("default")
    stored = redis.set(
        f"ws-ticket:{ticket}",
        json.dumps({"user_id": str(user_id), "game_id": str(game_id)}),
        ex=settings.JWT_WS_TICKET_TTL_SECONDS,
        nx=True,
    )
    if not stored:
        raise RuntimeError("Impossible de créer un ticket WebSocket unique.")
    return ticket
