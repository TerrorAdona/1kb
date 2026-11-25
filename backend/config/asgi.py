import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

from channels.routing import ProtocolTypeRouter, URLRouter
from channels.security.websocket import OriginValidator
from django.core.asgi import get_asgi_application
from django.conf import settings

django_asgi_app = get_asgi_application()

from apps.realtime.routing import websocket_urlpatterns

application = ProtocolTypeRouter(
    {
        "http": django_asgi_app,
        "websocket": OriginValidator(
            URLRouter(websocket_urlpatterns), settings.FRONTEND_ORIGINS
        ),
    }
)
