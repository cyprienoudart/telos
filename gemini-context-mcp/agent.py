"""
Agentic loop powered by OpenRouter (OpenAI-compatible API).

Architecture is unchanged from the Gemini version:
- One OpenAI client initialised at module load (lazy, on first use).
- INNER_TOOLS are plain Python callables; their JSON schemas are defined
  explicitly as _TOOL_SCHEMAS for the OpenAI function-calling format.
- Manual multi-turn loop: execute tool calls until finish_reason == "stop".
- Images / PDFs returned by read_file() are intercepted in _dispatch() and
  described via a separate one-shot vision call before being injected back
  into the conversation as plain text.
"""

from __future__ import annotations

import base64
import os
from typing import Any

import openai

from tools import (
    _MULTIMODAL_SENTINEL,
    file_info,
    grep,
    list_files,
    read_file,
)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

_BASE_URL = "https://openrouter.ai/api/v1"
# Any OpenRouter model that supports function calling works here.
# See https://openrouter.ai/models for the full list.
_MODEL = os.environ.get("OPENROUTER_MODEL", "google/gemini-2.0-flash-001")
_MAX_ITERATIONS = 20

_SYSTEM_PROMPT = """\
You are a precise research assistant with access to a local context store \
containing documents, source code, images, and PDFs.

Use the provided tools to explore and read files as needed to answer the \
user's question accurately and completely. When you have gathered enough \
information, return a clear, well-structured answer in Markdown.

Rules:
- Always check what files exist before trying to read them.
- Read relevant files before forming conclusions.
- If the answer requires synthesising multiple files, do so.
- If a file is not relevant, skip it.
- If you cannot find the answer, say so clearly.
"""

# ---------------------------------------------------------------------------
# OpenAI-format tool schemas (one per inner tool)
# ---------------------------------------------------------------------------

_TOOL_SCHEMAS: list[dict] = [
    {
        "type": "function",
        "function": {
            "name": "list_files",
            "description": (
                "List all files in a directory (relative to the context store root), "
                "recursively. Returns a newline-separated list of relative paths, or "
                "an error string."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "directory": {
                        "type": "string",
                        "description": (
                            "Path to list, relative to the context store root. "
                            "Defaults to the root itself ('.')."
                        ),
                    }
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": (
                "Read a file from the context store. "
                "For text files: returns the content (capped at 80,000 characters). "
                "For images and PDFs: returns a detailed description of the visual content."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "File path relative to the context store root.",
                    }
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "grep",
            "description": (
                "Search for a regex pattern across all text files in a directory, "
                "recursively. Skips binary files. Returns up to 50 results in "
                "path:line_number: matched_line format."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "pattern": {
                        "type": "string",
                        "description": "Regular expression to search for.",
                    },
                    "directory": {
                        "type": "string",
                        "description": (
                            "Directory to search, relative to the context store root. "
                            "Defaults to the root."
                        ),
                    },
                },
                "required": ["pattern"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "file_info",
            "description": (
                "Return metadata about a file or directory: size, modification time, "
                "MIME type, and whether it is text or binary/multimodal."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Path relative to the context store root.",
                    }
                },
                "required": ["path"],
            },
        },
    },
]

# ---------------------------------------------------------------------------
# Client (lazy singleton)
# ---------------------------------------------------------------------------

_client: openai.OpenAI | None = None


def _get_client() -> openai.OpenAI:
    global _client
    if _client is None:
        api_key = os.environ.get("OPENROUTER_API_KEY")
        if not api_key:
            raise RuntimeError(
                "OPENROUTER_API_KEY environment variable is not set. "
                "Copy .env.example to .env and add your key."
            )
        _client = openai.OpenAI(
            base_url=_BASE_URL,
            api_key=api_key,
            default_headers={"X-Title": "gemini-context-mcp"},
        )
    return _client


# ---------------------------------------------------------------------------
# Multimodal description helper
# ---------------------------------------------------------------------------

def _describe_multimodal(data: bytes, mime_type: str, path: str) -> str:
    """
    Send image / PDF bytes to the model in a one-shot call and return a
    plain-text description. Keeps the main agentic loop text-only.
    """
    client = _get_client()
    b64 = base64.standard_b64encode(data).decode()
    data_url = f"data:{mime_type};base64,{b64}"

    prompt = (
        f"Describe the contents of this file ('{path}') in detail. "
        "Extract all text, key information, diagrams, tables, and visual elements. "
        "Format your response as structured Markdown."
    )

    try:
        response = client.chat.completions.create(
            model=_MODEL,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "image_url", "image_url": {"url": data_url}},
                        {"type": "text", "text": prompt},
                    ],
                }
            ],
        )
        return response.choices[0].message.content or "(no description returned)"
    except Exception as exc:  # noqa: BLE001
        return f"(Could not describe '{path}': {exc})"


# ---------------------------------------------------------------------------
# Function dispatch
# ---------------------------------------------------------------------------

_TOOL_MAP: dict[str, Any] = {
    "list_files": list_files,
    "read_file": read_file,
    "grep": grep,
    "file_info": file_info,
}


def _dispatch(name: str, args: dict[str, Any]) -> str:
    """
    Call the named inner tool with *args* and return a string result.
    Intercepts the multimodal sentinel and replaces it with a text description.
    """
    fn = _TOOL_MAP.get(name)
    if fn is None:
        return f"ERROR: Unknown tool '{name}'."

    result = fn(**args)

    # Intercept multimodal sentinel
    if isinstance(result, tuple) and result[0] == _MULTIMODAL_SENTINEL:
        _, data, mime_type, path = result
        description = _describe_multimodal(data, mime_type, path)
        return f"[Multimodal file: {path}]\n\n{description}"

    return str(result)


# ---------------------------------------------------------------------------
# Agentic loop
# ---------------------------------------------------------------------------

def run_agent(question: str) -> str:
    """
    Run the agentic loop to answer *question* using the context store.
    Returns a Markdown string answer (or an error message).
    """
    client = _get_client()

    messages: list[dict] = [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {"role": "user", "content": question},
    ]

    for _ in range(_MAX_ITERATIONS):
        response = client.chat.completions.create(
            model=_MODEL,
            messages=messages,
            tools=_TOOL_SCHEMAS,
            tool_choice="auto",
        )

        choice = response.choices[0]
        msg = choice.message

        # Append the assistant turn to history
        messages.append(msg.model_dump(exclude_none=True))

        # No tool calls → model is done
        if not msg.tool_calls:
            return msg.content or "(no text response)"

        # Execute each tool call and append results
        for tc in msg.tool_calls:
            import json
            args = json.loads(tc.function.arguments) if tc.function.arguments else {}
            result_text = _dispatch(tc.function.name, args)
            messages.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "content": result_text,
            })

    return (
        f"ERROR: Agent exceeded {_MAX_ITERATIONS} iterations without completing. "
        "The question may be too complex or the context store too large."
    )


# ---------------------------------------------------------------------------
# Simpler direct-file helper (used by get_context_file outer tool)
# ---------------------------------------------------------------------------

def describe_file(filename: str, focus: str = "") -> str:
    """
    Retrieve and describe a specific file from the context store.

    For text files: returns the content directly (with optional focus summary).
    For multimodal files: returns a vision description.
    If *focus* is provided, asks the model to summarise with that focus.
    """
    result = read_file(filename)

    if isinstance(result, str) and result.startswith("ERROR:"):
        return result

    if isinstance(result, tuple) and result[0] == _MULTIMODAL_SENTINEL:
        _, data, mime_type, path = result
        return _describe_multimodal(data, mime_type, path)

    text = str(result)
    if not focus:
        return text

    client = _get_client()
    try:
        response = client.chat.completions.create(
            model=_MODEL,
            messages=[
                {
                    "role": "user",
                    "content": (
                        f"The following is the content of '{filename}'.\n\n"
                        f"{text}\n\n"
                        f"Focus: {focus}\n\n"
                        "Summarise the relevant parts of this file based on the focus above."
                    ),
                }
            ],
        )
        return response.choices[0].message.content or text
    except Exception as exc:  # noqa: BLE001
        return f"(Could not summarise with focus — returning raw content)\n\n{text}\n\nError: {exc}"
