"""
ASGI config for smartmirror project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/5.2/howto/deployment/asgi/
"""

import os
import logging

from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack

from mirror.services import MCPService
import ml_models.routing

logger = logging.getLogger(__name__)

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'smartmirror.settings')

django_asgi_app = get_asgi_application()
mcp_service_instance = None

async def lifespan_handler(scope, receive, send):
    global mcp_service_instance
    while True:
        message = await receive()
        if message['type'] == 'lifespan.startup':
            try:
                logger.info("Lifespan startup: Initializing MCPService...")
                mcp_service_instance = await MCPService.get_instance()
                await mcp_service_instance.connect()
                await send({'type': 'lifespan.startup.complete'})
                logger.info("MCPService startup complete.")
            except Exception as e:
                logger.error(f"Error during MCPService startup: {e}", exc_info=True)
                await send({'type': 'lifespan.startup.failed', 'message': str(e)})
        elif message['type'] == 'lifespan.shutdown':
            try:
                logger.info("Lifespan shutdown: Shutting down MCPService...")
                if mcp_service_instance:
                    await mcp_service_instance.shutdown()
                await send({'type': 'lifespan.shutdown.complete'})
                logger.info("MCPService shutdown complete.")
            except Exception as e:
                logger.error(f"Error during MCPService shutdown: {e}", exc_info=True)
                await send({'type': 'lifespan.shutdown.failed', 'message': str(e)})
            return

# Get WebSocket URL patterns directly from ml_modelsrouting
# Ensure ml_models.routing defines a list named 'websocket_urlpatterns'
websocket_routes = getattr(ml_models.routing, 'websocket_urlpatterns', [])

if not websocket_routes:
    logger.warning("No WebSocket URL patterns found in ml_models.routing. WebSockets may not be handled.")

application = ProtocolTypeRouter({
    "http": django_asgi_app,
    "websocket": AuthMiddlewareStack(
        URLRouter(
            websocket_routes  # Use the routes from ml_models.routing directly
        )
    ),
    "lifespan": lifespan_handler,
})

def get_mcp_service():
    return mcp_service_instance
