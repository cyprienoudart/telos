"""
Gemini Context MCP Server — two tools exposed to Claude.

Tools
-----
  summarize()              → 15-bullet plain-English overview (cached)
  answer_question(query)   → 1-5 sentence plain-English answer

Run:
    python server.py
    # → http://127.0.0.1:8000/sse

Claude Desktop config:
    { "mcpServers": { "gemini-context": { "url": "http://localhost:8000/sse" } } }
"""

from __future__ import annotations

import os

from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

load_dotenv()

import agent  # noqa: E402  (needs load_dotenv first)

# ---------------------------------------------------------------------------
# FastMCP app
# ---------------------------------------------------------------------------

_host = os.environ.get("MCP_HOST", "127.0.0.1")
_port = int(os.environ.get("MCP_PORT", "8000"))

mcp = FastMCP("gemini-context", host=_host, port=_port)


# ---------------------------------------------------------------------------
# Tool 1 — summarize
# ---------------------------------------------------------------------------

@mcp.tool()
def summarize() -> str:
    """
    Summarise the entire knowledge base in 15 plain-English bullet points.

    Written for a non-technical reader: no code, no jargon, no low-level
    details. Result is cached — repeated calls are instant unless the files
    have changed.
    """
    try:
        return agent.summarize()
    except Exception as exc:  # noqa: BLE001
        return f"ERROR: {exc}"


# ---------------------------------------------------------------------------
# Tool 2 — answer_question
# ---------------------------------------------------------------------------

@mcp.tool()
def answer_question(query: str) -> str:
    """
    Answer a question about the knowledge base in 1-5 plain-English sentences.

    Written for a non-technical reader. If the answer is not in the knowledge
    base, says so simply. Do not use for questions unrelated to the project.

    Args:
        query: The question to answer.
    """
    try:
        return agent.answer_question(query)
    except Exception as exc:  # noqa: BLE001
        return f"ERROR: {exc}"


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    mcp.run(transport="sse")
