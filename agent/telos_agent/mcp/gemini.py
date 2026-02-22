"""Gemini Context MCP server — provides summarize/answerQuestion tools.

Runs as a stdio MCP server. Interview, planning, PRD generation, and
orchestrator agents use these tools to access the Gemini context window.
Subagents and the reviewer do NOT have access.

Placeholder implementation — real Gemini integration TBD.
"""

import os
from pathlib import Path

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("gemini-context")

CONTEXT_DIR = Path(os.environ.get("CONTEXT_DIR", "."))


@mcp.tool()
def summarize() -> str:
    """Summarize the current project context from Gemini's context window.

    Returns a summary of what Gemini knows about the project, including
    any multimodal context (designs, PDFs, diagrams) that have been loaded.
    """
    # Placeholder: list files in context dir
    if not CONTEXT_DIR.exists():
        return "No context directory found."

    files = sorted(CONTEXT_DIR.iterdir())
    if not files:
        return "Context directory is empty."

    listing = "\n".join(f"- {f.name}" for f in files if f.is_file())
    return f"Context files available:\n{listing}\n\n(Gemini integration pending — this is a placeholder response)"


@mcp.tool()
def answer_question(query: str) -> str:
    """Ask Gemini a question about the project context.

    Uses Gemini's large context window to answer questions about the project,
    including information from designs, documents, and other multimodal sources.

    Args:
        query: The question to ask about the project context.
    """
    return (
        f"Question received: {query}\n\n"
        "(Gemini integration pending — this is a placeholder. "
        "When connected, Gemini will answer using its full context window "
        "including any loaded documents, designs, and project files.)"
    )


if __name__ == "__main__":
    mcp.run()
