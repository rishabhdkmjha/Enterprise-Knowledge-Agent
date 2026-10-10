import json
import os
import sys
from contextlib import AsyncExitStack

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


class MCPTools:
    """Keeps one long-lived session to the MCP server subprocess."""

    def __init__(self):
        self.session: ClientSession | None = None
        self._stack: AsyncExitStack | None = None

    async def start(self):
        self._stack = AsyncExitStack()
        params = StdioServerParameters(
            command=sys.executable, args=["-m", "app.mcp_server"], env=dict(os.environ))
        read, write = await self._stack.enter_async_context(stdio_client(params))
        self.session = await self._stack.enter_async_context(ClientSession(read, write))
        await self.session.initialize()

    async def stop(self):
        if self._stack:
            await self._stack.aclose()

    async def call(self, name: str, args: dict | None = None):
        res = await self.session.call_tool(name, args or {})
        text = "".join(c.text for c in res.content if getattr(c, "text", None))
        return json.loads(text)


tools = MCPTools()
