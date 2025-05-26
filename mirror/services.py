# mirror/services.py
import asyncio
import os
import logging
from django.conf import settings
from .mcp_client import MCPClient  # Make sure this import path is correct

logger = logging.getLogger(__name__)


class MCPService:
    _instance = None
    _lock = asyncio.Lock()  # To ensure thread-safe singleton instantiation

    def __init__(self):
        # This constructor should ideally only be called once via get_instance
        self.client = MCPClient()
        self.is_connected = False
        # The AsyncExitStack is now part of MCPClient, which is good.

    @classmethod
    async def get_instance(cls):
        # Ensure singleton creation is async-safe if multiple parts of your app try to get it concurrently at startup
        if cls._instance is None:
            async with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    async def connect(self):
        if not self.client.session:  # Or use a more robust self.is_connected flag
            server_script_path = os.path.join(
                settings.BASE_DIR, "mirror", "mirrordb_server.py"
            )
            logger.info("Attempting to connect MCP client...")
            try:
                # The connect_to_server method in your MCPClient already handles
                # entering the async contexts for stdio_client and ClientSession.
                await self.client.connect_to_server(server_script_path)
                self.is_connected = True  # Set based on successful connection
                logger.info("MCP client connected successfully.")
            except Exception as e:
                logger.error(
                    f"Failed to connect MCP client during startup: {e}", exc_info=True
                )
                self.is_connected = False
                raise  # Re-raise to signal startup failure if critical
        else:
            logger.info("MCP client session already exists.")

    async def shutdown(self):
        if self.client:
            logger.info("Shutting down MCP client...")
            await self.client.cleanup()  # MCPClient.cleanup() calls self.exit_stack.aclose()
            self.is_connected = False
            logger.info("MCP client shut down successfully.")

    async def process_query(self, query: str) -> str:
        if not self.client.session or not self.is_connected:
            # If not connected, you might try a one-off reconnect here,
            # but it's generally better to ensure it's connected at startup
            # and remains so. For now, we'll raise an error.
            logger.error("MCP Client is not connected. Query processing aborted.")
            raise Exception(
                "MCP Client is not connected. Please ensure the service is running."
            )

        # The process_query method in MCPClient will use the existing session
        return await self.client.process_query(query)


# This function will be used by views to get the service instance
async def get_mcp_service():
    service = await MCPService.get_instance()
    # It's assumed connect() is called during ASGI startup.
    # If there's a chance of disconnection, add a check and reconnect attempt here or in process_query.
    if not service.is_connected and not service.client.session:
        logger.warning("MCPService not connected. Attempting to connect on demand.")
        try:
            await service.connect()  # Try to connect if not already
        except Exception as e:
            logger.error(
                f"On-demand connection failed for MCPService: {e}", exc_info=True
            )
            raise  # Fail if on-demand connection doesn't work
    return service
