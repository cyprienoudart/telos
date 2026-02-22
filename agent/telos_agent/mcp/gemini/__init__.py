"""Gemini Context MCP server — RAG pipeline over a local knowledge base.

Re-exports the FastMCP app and tool functions so existing imports like
``from telos_agent.mcp.gemini import mcp`` continue to work.
"""

from .server import answer_question, mcp, summarize

__all__ = ["mcp", "summarize", "answer_question"]
