"""
ASGI config for smartmirror project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/5.2/howto/deployment/asgi/
"""

import os

from django.core.asgi import get_asgi_application
from mirror.services import MCPService # Assuming 'mirror' is your app name

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'smartmirror.settings')

django_asgi_app = get_asgi_application()

# Store the service instance. This is okay here as asgi.py is module-level.
mcp_service_instance = None

async def application(scope, receive, send):
    global mcp_service_instance

    if scope['type'] == 'lifespan':
        while True:
            message = await receive()
            if message['type'] == 'lifespan.startup':
                try:
                    # Get and store the singleton instance
                    mcp_service_instance = await MCPService.get_instance()
                    await mcp_service_instance.connect() # Connect the client
                    await send({'type': 'lifespan.startup.complete'})
                except Exception as e:
                    # Log the error appropriately
                    print(f"Error during MCPService startup: {e}") # Or use proper logging
                    await send({'type': 'lifespan.startup.failed', 'message': str(e)})
            elif message['type'] == 'lifespan.shutdown':
                try:
                    if mcp_service_instance:
                        await mcp_service_instance.shutdown() # Clean up the client
                    await send({'type': 'lifespan.shutdown.complete'})
                except Exception as e:
                    print(f"Error during MCPService shutdown: {e}") # Or use proper logging
                    await send({'type': 'lifespan.shutdown.failed', 'message': str(e)})
                return # Important to exit the loop
    elif scope['type'] == 'http':
        # For HTTP requests, Django's app will handle it.
        # Views can get the mcp_service_instance via the get_mcp_service() helper.
        await django_asgi_app(scope, receive, send)
    else:
        # Handle other scope types if necessary, or pass to Django's app
        await django_asgi_app(scope, receive, send)
