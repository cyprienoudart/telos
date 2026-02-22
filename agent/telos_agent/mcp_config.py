"""Dynamic MCP config generator.

Builds MCP server configuration JSON on the fly, replacing the static
config/mcp-servers.json template approach. Each phase of the workflow
requests only the servers it needs via boolean flags.
"""

import json
import os
import tempfile
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env")


def generate_mcp_config(
    agent_dir: Path,
    project_dir: Path,
    context_dir: Path | None = None,
    include_gemini: bool = False,
    include_reviewer: bool = False,
    include_twenty_crm: bool = False,
) -> Path:
    """Generate an MCP config file with the requested servers.

    Server definitions use the same uv-based invocation pattern as before,
    but are built programmatically instead of read from a template.

    Returns the path to a temporary JSON config file.
    """
    servers: dict = {}

    if include_gemini:
        ctx = str(context_dir) if context_dir else str(project_dir)
        servers["gemini-context"] = {
            "command": "uv",
            "args": [
                "--directory", str(agent_dir),
                "run", "python", "-m", "telos_agent.mcp.gemini",
            ],
            "env": {
                "CONTEXT_DIR": ctx,
            },
        }

    if include_reviewer:
        servers["reviewer"] = {
            "command": "uv",
            "args": [
                "--directory", str(agent_dir),
                "run", "python", "-m", "telos_agent.mcp.reviewer",
            ],
            "env": {
                "VERDICT_PATH": str(project_dir / "verdict.json"),
            },
        }

    if include_twenty_crm:
        twenty_url = os.environ.get("TWENTY_API_URL", "http://localhost:3000")
        twenty_key = os.environ.get("TWENTY_API_KEY", "")
        servers["twenty-crm"] = {
            "command": "npx",
            "args": ["-y", "twenty-mcp-server"],
            "env": {
                "TWENTY_API_KEY": twenty_key,
                "TWENTY_BASE_URL": twenty_url,
            },
        }

    config = {"mcpServers": servers}

    tmp = tempfile.NamedTemporaryFile(
        mode="w", suffix=".json", prefix="telos-mcp-", delete=False,
    )
    tmp.write(json.dumps(config, indent=2))
    tmp.close()
    return Path(tmp.name)
