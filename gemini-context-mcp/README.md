# Gemini Context MCP Server

A standalone [Model Context Protocol](https://modelcontextprotocol.io/) server
that lets Claude (or any MCP client) query a **local context store** — documents,
source code, PDFs, and images — without giving Claude direct filesystem access.

The pipeline is: embed context with FastEmbed → index with ChromaDB → retrieve
relevant chunks → answer via an OpenRouter LLM (Gemini 2.0 Flash by default).

```
Claude ──(MCP/SSE)──► server.py ──► agent.py ──► OpenRouter (Gemini 2.0 Flash)
                                        │
                                   FastEmbed + ChromaDB
                                        │
                                    context/ (local files)
```

---

## Quickstart

### 1. Prerequisites

- Python 3.13+
- An [OpenRouter API key](https://openrouter.ai/keys) (free tier works)

### 2. Set up the environment

```bash
cd gemini-context-mcp
uv venv .venv
source .venv/bin/activate       # macOS / Linux
# source .venv/Scripts/activate # Windows (Git Bash / MSYS2)

uv pip install -r requirements.txt
```

### 3. Configure

```bash
cp .env.example .env
# Edit .env and set OPENROUTER_API_KEY=your_actual_key
```

### 4. Start the server

```bash
python server.py
# → INFO: Uvicorn running on http://127.0.0.1:8000
```

---

## MCP Tools

| Tool | Description |
|------|-------------|
| `summarize()` | 15-bullet plain-English overview of the entire context store (cached in memory) |
| `answer_question(query)` | 1–5 sentence plain-English answer using retrieved context (semantically cached) |

### `answer_question()` pipeline

1. Embed the query with FastEmbed
2. Semantic cache lookup — instant return on hit (≥ 0.85 cosine similarity)
3. Dense retrieval — top 3 chunks from ChromaDB
4. LLM call via OpenRouter — answer in 1–5 plain-English sentences
5. Store answer in the semantic cache

### `summarize()` pipeline

1. Collect the **first chunk per file** from the context store
2. Single LLM call to produce 15 bullet points
3. Cached in memory until files change (detected via content hash)

> **Note:** `summarize()` uses only the first chunk per file, so very large files
> may not be fully represented in the summary.

---

## Sample Data

The `context/` directory contains demo data for testing:

- `docs/team.md` — fictional team roster
- `docs/priorities.md` — sprint priorities and bugs
- `docs/README.md` — project overview
- `docs/whiteboard.jpg` — sample image (tests multimodal pipeline)
- `codebase/src/` — sample Python source files

This data is used by the integration test and benchmark by default.

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

## Configuration Reference

| Variable | Default | Description |
|----------|---------|-------------|
| `OPENROUTER_API_KEY` | *(required)* | Your OpenRouter API key |
| `CONTEXT_DIR` | `./context` | Path to the context store directory |
| `OPENROUTER_MODEL` | `google/gemini-2.0-flash-001` | LLM model for answering/summarizing |
| `VISION_MODEL` | Same as `OPENROUTER_MODEL` | Model for image/PDF description (must support vision) |
| `FASTEMBED_MODEL` | `BAAI/bge-small-en-v1.5` | Embedding model for FastEmbed |
| `CHROMA_DIR` | `~/.cache/gemini-context-mcp/chroma` | ChromaDB persistence directory |
| `MCP_HOST` | `127.0.0.1` | Server bind host |
| `MCP_PORT` | `8000` | Server bind port |

---

## Testing

```bash
# Unit tests (no API key needed)
uv pip install -r requirements-dev.txt
python -m pytest tests/ -v -m "not integration"

# Integration test (requires OPENROUTER_API_KEY in .env)
python tests/test_integration.py

# Benchmark (requires OPENROUTER_API_KEY in .env)
python tests/benchmark.py
```

---

## Concurrency

The server is single-threaded. FastMCP handles one request at a time.
ChromaDB, the embedding model, and the LLM client are all initialized
as lazy singletons — there is no thread-safety machinery. This is fine
for local/single-user use. For concurrent access, run behind a process
manager (e.g. `gunicorn` with workers) or add locking.

---

## Architecture Notes

- **No agentic loop**: The server uses a simple RAG pipeline — embed, retrieve,
  answer. There is no multi-turn tool-calling loop.
- **Multimodal**: Images are described by a vision LLM. PDFs are processed with
  pypdf for text extraction; image-heavy pages are sent to the vision model
  via OpenRouter's file content type.
- **Semantic cache**: Query embeddings are compared against previously asked
  questions. If cosine similarity exceeds 0.85, the cached answer is returned
  without an LLM call.
- **Content hashing**: An MD5 hash over file sizes + mtimes detects changes.
  When files change, both the context index and semantic cache are rebuilt.
