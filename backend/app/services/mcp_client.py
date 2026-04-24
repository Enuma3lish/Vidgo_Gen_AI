"""
MCP Client Manager — manages connections to Pollo.ai and PiAPI MCP servers.

Each MCP server runs as a Node.js subprocess via stdio transport.
The manager handles lifecycle (start, reconnect, shutdown) and provides
a simple interface for providers to call MCP tools.

Requires:
  - npm packages installed globally: pollo-mcp, piapi-mcp-server (built)
  - Environment: POLLO_API_KEY, PIAPI_KEY
"""
import asyncio
import logging
import os
from typing import Any, Dict, List, Optional

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

logger = logging.getLogger(__name__)


class MCPServerConnection:
    """Manages a single MCP server subprocess + session."""

    def __init__(self, name: str, server_params: StdioServerParameters):
        self.name = name
        self.server_params = server_params
        self._session: Optional[ClientSession] = None
        self._read = None
        self._write = None
        self._context = None
        self._session_context = None
        self._tools: List[Dict[str, Any]] = []
        self._lock = asyncio.Lock()
        self._connected = False

    @property
    def connected(self) -> bool:
        return self._connected and self._session is not None

    async def connect(self) -> bool:
        """Start MCP server subprocess and initialize session."""
        async with self._lock:
            if self._connected:
                return True
            try:
                logger.info(f"[MCP:{self.name}] Starting server...")
                self._context = stdio_client(self.server_params)
                self._read, self._write = await self._context.__aenter__()

                self._session_context = ClientSession(self._read, self._write)
                self._session = await self._session_context.__aenter__()
                await self._session.initialize()

                # Cache available tools
                tools_result = await self._session.list_tools()
                self._tools = [
                    {"name": t.name, "description": t.description}
                    for t in tools_result.tools
                ]
                self._connected = True
                tool_names = [t["name"] for t in self._tools]
                logger.info(f"[MCP:{self.name}] Connected. Tools: {tool_names}")
                return True
            except Exception as e:
                logger.error(f"[MCP:{self.name}] Failed to connect: {e}")
                self._connected = False
                await self._cleanup()
                return False

    async def disconnect(self):
        """Shut down MCP server."""
        async with self._lock:
            self._connected = False
            await self._cleanup()
            logger.info(f"[MCP:{self.name}] Disconnected.")

    async def _cleanup(self):
        """Clean up session and context."""
        try:
            if self._session_context:
                await self._session_context.__aexit__(None, None, None)
        except Exception:
            pass
        try:
            if self._context:
                await self._context.__aexit__(None, None, None)
        except Exception:
            pass
        self._session = None
        self._session_context = None
        self._context = None
        self._read = None
        self._write = None

    async def call_tool(
        self, tool_name: str, arguments: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Call an MCP tool. Auto-reconnects on failure."""
        if not self._connected:
            if not await self.connect():
                raise ConnectionError(f"[MCP:{self.name}] Not connected")

        try:
            result = await self._session.call_tool(tool_name, arguments)
            # Parse MCP result content
            if result.content:
                # MCP returns list of content blocks; combine text blocks
                texts = [
                    block.text for block in result.content
                    if hasattr(block, "text")
                ]
                combined = "\n".join(texts)
                # Try JSON parse
                import json
                try:
                    return json.loads(combined)
                except (json.JSONDecodeError, ValueError):
                    return {"raw": combined}
            return {"raw": str(result)}
        except Exception as e:
            logger.error(f"[MCP:{self.name}] Tool '{tool_name}' failed: {e}")
            # Attempt reconnect for next call
            self._connected = False
            await self._cleanup()
            raise

    def list_tools(self) -> List[Dict[str, Any]]:
        """Return cached list of available tools."""
        return self._tools


class MCPClientManager:
    """
    Singleton manager for all MCP server connections.

    Usage:
        manager = get_mcp_manager()
        await manager.startup()
        result = await manager.call("pollo", "text2video", {"prompt": "..."})
        await manager.shutdown()
    """

    def __init__(self):
        self._servers: Dict[str, MCPServerConnection] = {}
        self._started = False

    def _build_server_params(self) -> Dict[str, StdioServerParameters]:
        """Build MCP server configurations from environment."""
        servers = {}

        pollo_key = os.getenv("POLLO_API_KEY", "")
        if pollo_key:
            pollo_env = {
                **os.environ,
                "POLLO_AI_API_KEY": pollo_key,
                "POLLO_AI_BASE_URL": os.getenv("POLLO_AI_BASE_URL", "https://pollo.ai"),
                "POLLO_AI_HOME_DIR": os.getenv("POLLO_AI_HOME_DIR", "/tmp/pollo_videos"),
            }
            # Optional: restrict which models are loaded as MCP tools
            if os.getenv("POLLO_AI_VIDEO_MODEL_TEXT"):
                pollo_env["POLLO_AI_VIDEO_MODEL_TEXT"] = os.getenv("POLLO_AI_VIDEO_MODEL_TEXT")
            if os.getenv("POLLO_AI_VIDEO_MODEL_IMG"):
                pollo_env["POLLO_AI_VIDEO_MODEL_IMG"] = os.getenv("POLLO_AI_VIDEO_MODEL_IMG")

            servers["pollo"] = StdioServerParameters(
                command="npx",
                args=["-y", "mcp-server-pollo"],
                env=pollo_env,
            )

        piapi_key = os.getenv("PIAPI_KEY", "")
        piapi_mcp_enabled = os.getenv("PIAPI_MCP_ENABLED", "false").lower() in {"1", "true", "yes", "on"}
        piapi_mcp_path = os.getenv(
            "PIAPI_MCP_PATH", "/app/mcp-servers/piapi-mcp-server/dist/index.js"
        )
        if piapi_key and piapi_mcp_enabled:
            servers["piapi"] = StdioServerParameters(
                command="node",
                args=[piapi_mcp_path],
                env={
                    **os.environ,
                    "PIAPI_API_KEY": piapi_key,
                },
            )

        return servers

    async def startup(self):
        """Start all configured MCP servers."""
        if self._started:
            return

        params_map = self._build_server_params()
        for name, params in params_map.items():
            conn = MCPServerConnection(name, params)
            self._servers[name] = conn
            # Connect in background — don't block app startup
            asyncio.create_task(self._connect_with_retry(conn))

        self._started = True
        logger.info(f"[MCPManager] Startup initiated for: {list(params_map.keys())}")

    async def _connect_with_retry(self, conn: MCPServerConnection, max_retries: int = 3):
        """Try connecting with retries."""
        for attempt in range(1, max_retries + 1):
            if await conn.connect():
                return
            logger.warning(
                f"[MCPManager] {conn.name} connect attempt {attempt}/{max_retries} failed"
            )
            await asyncio.sleep(5 * attempt)
        logger.error(f"[MCPManager] {conn.name} failed after {max_retries} retries")

    async def shutdown(self):
        """Disconnect all MCP servers."""
        for conn in self._servers.values():
            await conn.disconnect()
        self._servers.clear()
        self._started = False
        logger.info("[MCPManager] All servers shut down.")

    async def call(
        self, server_name: str, tool_name: str, arguments: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Call a tool on a specific MCP server."""
        conn = self._servers.get(server_name)
        if not conn:
            raise ValueError(f"MCP server '{server_name}' not configured")
        return await conn.call_tool(tool_name, arguments)

    def is_available(self, server_name: str) -> bool:
        """Check if an MCP server is connected and available."""
        conn = self._servers.get(server_name)
        return conn is not None and conn.connected

    def list_tools(self, server_name: str) -> List[Dict[str, Any]]:
        """List available tools for a server."""
        conn = self._servers.get(server_name)
        if not conn:
            return []
        return conn.list_tools()

    def get_status(self) -> Dict[str, Any]:
        """Get status of all MCP servers."""
        return {
            name: {
                "connected": conn.connected,
                "tools": [t["name"] for t in conn.list_tools()],
            }
            for name, conn in self._servers.items()
        }


# ── Singleton ──

_manager_instance: Optional[MCPClientManager] = None


def get_mcp_manager() -> MCPClientManager:
    global _manager_instance
    if _manager_instance is None:
        _manager_instance = MCPClientManager()
    return _manager_instance
