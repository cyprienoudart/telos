"""
Gemini Context MCP Server

Exposes three tools to MCP clients (e.g. Claude Desktop):

  query_context(question)            → Gemini agentic answer
  list_context()                     → recursive file tree (no Gemini)
  get_context_file(filename, focus)  → direct file content / description

Run with:
    python server.py
    # → INFO: Uvicorn running on http://127.0.0.1:8000

Then connect Claude Desktop (or MCP Inspector) to:
    http://localhost:8000/sse
"""

from __future__ import annotations

import os

from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

load_dotenv()  # load .env before importing agent (needs GEMINI_API_KEY)

import agent  # noqa: E402
import tools  # noqa: E402

# ---------------------------------------------------------------------------
# FastMCP application
# ---------------------------------------------------------------------------

_host = os.environ.get("MCP_HOST", "127.0.0.1")
_port = int(os.environ.get("MCP_PORT", "8000"))

mcp = FastMCP("gemini-context", host=_host, port=_port)

# ---------------------------------------------------------------------------
# Tool 1: query_context
# ---------------------------------------------------------------------------

@mcp.tool()
def query_context(question: str) -> str:
    """
    Ask a natural-language question about the local context store.

    A Gemini agent will autonomously explore the context store (documents,
    source code, images, PDFs) using an internal tool loop and return a
    detailed Markdown answer.

    Args:
        question: The question to answer using the context store.
    """
    try:
        return agent.run_agent(question)
    except Exception as exc:  # noqa: BLE001
        return f"ERROR: Agent failed — {exc}"


# ---------------------------------------------------------------------------
# Tool 2: list_context
# ---------------------------------------------------------------------------

@mcp.tool()
def list_context() -> str:
    """
    List all files in the context store as a recursive tree.

    This tool does not call Gemini — it is fast, free, and deterministic.
    Use it to understand what is available before asking more specific questions.
    """
    try:
        file_list = tools.list_files(".")
        root = os.environ.get("CONTEXT_DIR", "./context")
        return f"Context store: {root}\n\n{file_list}"
    except Exception as exc:  # noqa: BLE001
        return f"ERROR: Could not list context store — {exc}"


# ---------------------------------------------------------------------------
# Tool 3: get_context_file
# ---------------------------------------------------------------------------

@mcp.tool()
def get_context_file(filename: str, focus: str = "") -> str:
    """
    Retrieve and return the content of a specific file from the context store.

    For text files the raw content is returned (capped at 80,000 characters).
    For images and PDFs, Gemini describes the visual content in Markdown.
    If *focus* is provided, Gemini summarises the file with that focus in mind.

    Args:
        filename: Path to the file, relative to the context store root.
        focus: Optional topic to focus on when summarising the file.
    """
    try:
        return agent.describe_file(filename, focus)
    except Exception as exc:  # noqa: BLE001
        return f"ERROR: Could not retrieve file '{filename}' — {exc}"


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    mcp.run(transport="sse")
