"""Reviewer MCP server — provides approve/deny verdict tools.

Runs as a stdio MCP server. The reviewer subagent calls these tools
to record its verdict, which the Ralph loop reads from verdict.json.
"""

import json
import os
from datetime import datetime, timezone
from pathlib import Path

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("reviewer-verdict")

VERDICT_PATH = Path(os.environ.get("VERDICT_PATH", "verdict.json"))


def _write_verdict(verdict: dict) -> None:
    verdict["timestamp"] = datetime.now(timezone.utc).isoformat()
    VERDICT_PATH.write_text(json.dumps(verdict, indent=2) + "\n")


@mcp.tool()
def approve(summary: str) -> str:
    """Approve the current work. Call this when ALL acceptance criteria are met, ALL tests pass, and the implementation is correct. Provide a summary of what was verified."""
    _write_verdict({"approved": True, "summary": summary})
    return f"APPROVED: {summary}"


@mcp.tool()
def deny(reason: str) -> str:
    """Deny the current work. Call this when ANYTHING is wrong. Provide specific, actionable reasons for denial so the issue can be fixed."""
    _write_verdict({"approved": False, "reason": reason})
    return f"DENIED: {reason}"


if __name__ == "__main__":
    mcp.run()
