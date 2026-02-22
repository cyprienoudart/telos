"""Entry point for ``python -m telos_agent.mcp.gemini`` (stdio transport)."""

from .server import mcp

mcp.run()
