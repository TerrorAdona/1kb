import logging

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.db import transaction

from .models import GameEvent

logger = logging.getLogger(__name__)


def record_game_event(
    game,
    event_type,
    actor=None,
    public_payload=None,
    private_payloads=None,
    request_id=None,
):
    game.state_version += 1
    game.save(update_fields=["state_version", "updated_at"])
    event = GameEvent.objects.create(
        game=game,
        sequence=game.state_version,
        actor=actor,
        actor_display_name=getattr(actor, "display_name", ""),
        request_id=request_id,
        event_type=event_type,
        public_payload=public_payload or {},
        private_payloads=private_payloads or {},
    )
    transaction.on_commit(
        lambda game_id=str(game.pk), event_id=str(event.pk): publish_game_event(
            game_id, event_id
        )
    )
    return event


def publish_game_event(game_id: str, event_id: str) -> None:
    try:
        event = GameEvent.objects.get(pk=event_id)
        channel_layer = get_channel_layer()
        if channel_layer is None:
            return
        async_to_sync(channel_layer.group_send)(
            f"game_{game_id.replace('-', '')}",
            {
                "type": "lobby.event",
                "event": {
                    "id": str(event.pk),
                    "sequence": event.sequence,
                    "event_type": event.event_type,
                    "actor_display_name": event.actor_display_name,
                    "public": event.public_payload,
                    "private": event.private_payloads,
                    "created_at": event.created_at.isoformat(),
                },
            },
        )
    except Exception:
        # La persistance ne doit pas échouer si Redis est momentanément indisponible.
        logger.exception("Impossible de publier l’événement de partie %s.", game_id)
