# Gemini Context MCP Server

A standalone [Model Context Protocol](https://modelcontextprotocol.io/) server
that lets Claude (or any MCP client) query a **local context store** — documents,
source code, PDFs, and images — without giving Claude direct filesystem access.

A Gemini agent autonomously explores the context store using an internal tool loop
and returns natural-language answers. Claude sees only the answer.

```
Claude ──(MCP/SSE)──► server.py ──► agent.py ──► Gemini 2.0 Flash
                                          │
                                          └──(tools)──► context/ (local files)
```

---

## Quickstart

### 1. Prerequisites

- Python 3.13+
- A [Gemini API key](https://aistudio.google.com/app/apikey) (free tier works)

### 2. Set up the environment

```bash
cd gemini-context-mcp
python -m venv .venv
source .venv/Scripts/activate   # Windows (Git Bash / MSYS2)
# source .venv/bin/activate     # macOS / Linux

pip install -r requirements.txt
```

### 3. Configure

```bash
cp .env.example .env
# Edit .env and set GEMINI_API_KEY=your_actual_key
```

### 4. (Optional) Add multimodal files

Drop sample files into `context/docs/` to test vision capabilities:
- `architecture.pdf` — any PDF document
- `whiteboard.jpg` — any JPEG or PNG image

### 5. Start the server

```bash
python server.py
# → INFO: Uvicorn running on http://0.0.0.0:8000
```

---

## MCP Tools

| Tool | Description | Gemini? |
|------|-------------|---------|
| `query_context(question)` | Ask anything about the context store | Yes |
| `list_context()` | List all files as a tree | No (free) |
| `get_context_file(filename, focus?)` | Get/describe a specific file | Only for multimodal or when focus is set |

---

## Connecting Claude Desktop

Add to your Claude Desktop config (`claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "gemini-context": {
      "url": "http://localhost:8000/sse"
    }
  }
}
```

Restart Claude Desktop. The tools will appear in the tool picker.

---

## Testing Without Claude Desktop

### 1. Path traversal tests (no API key needed)

```bash
# Activate venv first
python -c "import tools; print(tools.list_files('../../etc'))"
# → ERROR: Path '../../etc' is outside the context store or invalid.

python -c "import tools; print(tools.list_files('.'))"
# → codebase/src/auth/handler.py
#   codebase/src/main.py
#   ...
```

### 2. Direct agent test

```bash
python -c "
from dotenv import load_dotenv; load_dotenv()
import agent
print(agent.run_agent('Who is on the engineering team?'))
"
```

### 3. MCP Inspector (recommended)

```bash
# Server must be running
npx @modelcontextprotocol/inspector http://localhost:8000/sse
```

Open the Inspector UI, call `list_context` first (no API key), then `query_context`.

---

## Configuration Reference

| Variable | Default | Description |
|----------|---------|-------------|
| `GEMINI_API_KEY` | *(required)* | Your Gemini API key |
| `CONTEXT_DIR` | `./context` | Path to the context store directory |
| `GEMINI_MODEL` | `gemini-2.0-flash` | Gemini model to use |
| `MCP_HOST` | `127.0.0.1` | Server bind host |
| `MCP_PORT` | `8000` | Server bind port |

---

## Architecture Notes

- **Path safety**: `tools._safe_resolve()` is the single chokepoint. Every tool
  call goes through it. Symlink traversal is blocked by `Path.resolve()` +
  `relative_to(BASE_DIR)`.
- **Multimodal**: Images and PDFs return a `__MULTIMODAL__` sentinel from
  `read_file()`. The agent intercepts it in `_dispatch()` and makes a separate
  one-shot Gemini vision call, injecting the text description back into the loop.
  The main agentic loop stays text-only.
- **Manual function calling**: `AutomaticFunctionCallingConfig(disable=True)` gives
  full control over the multi-turn loop. Capped at 20 iterations.
- **No Gemini for `list_context`**: The outer `list_context` tool calls
  `tools.list_files()` directly — no API cost, always deterministic.
- **Error handling**: All outer MCP tools catch all exceptions and return error
  strings. MCP tools must never raise.

---

## Security Considerations

This server is intended for local / trusted network use. Before exposing it:

- Bind to `127.0.0.1` instead of `0.0.0.0` if only used locally.
- Add authentication middleware if exposing over a network.
- The Gemini API key is read from the environment; never commit `.env`.
- The context store is readable by anyone who can reach the MCP server.
