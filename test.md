# Telos Backend Integration Test

## Test Scenario: International Women's Day Marketing Campaign

### Prompt
We need to create a marketing campaign for International Women's Day. We have to edit the landing page and send out email campaigns to all the women in our database with a discount. Both the website and email campaign have to include a relevant AI-generated image.

### Test Flow (Backend API — no frontend required)

The backend runs on `http://localhost:8000`. Below is the full sequence of API calls the frontend makes internally, reproduced with `curl`.

---

#### 0. Health check

```bash
curl http://localhost:8000/health
```

Expected: `{"status":"ok"}`

---

#### 1. Start conversation

```bash
curl -X POST http://localhost:8000/api/conversation/start \
  -H "Content-Type: application/json" \
  -d '{
    "message": "We need to create a marketing campaign for International Womans Day. We have to edit the landing page and send out email campaigns to all the women in our database with a discount. Both the website and email campaign has to include a relevant AI generated image."
  }'
```

**Response fields:**
- `session_id` — use this for all subsequent calls
- `first_question` — Ali's first follow-up question
- `coverage` / `initial_coverage` — how much the system already knows (0.0–1.0)
- `done` — if true, no more questions needed (unlikely on first call)
- `categories` — detected project types (e.g. `["landing_page", "email_marketing"]`)

---

#### 2. Answer questions (loop until `done: true`)

```bash
# Replace SESSION_ID with the actual session_id from step 1
curl -X POST http://localhost:8000/api/conversation/SESSION_ID/answer \
  -H "Content-Type: application/json" \
  -d '{
    "answer": "YOUR ANSWER TO THE QUESTION HERE"
  }'
```

**Suggested answers for this test scenario:**

| Question Topic | Example Answer |
|---|---|
| Target audience | Women aged 25-45 who are existing customers in our CRM database |
| Design style | Modern, elegant, empowering. Purple and gold color scheme |
| Email platform | We use Mailchimp for email campaigns |
| Landing page tech | Our website is built with Next.js, hosted on Vercel |
| Discount details | 20% off all products with code WOMENSDAY2026, valid March 1-15 |
| Brand tone | Empowering, celebratory, warm and inclusive |
| Key message | Celebrate the women who inspire us — treat yourself with 20% off |
| Timeline | Campaign should launch March 1st, landing page update by Feb 28th |
| Deliverables | Updated landing page hero section, email blast with image, social media assets |
| AI image style | Professional, diverse women in empowering poses, floral elements, purple/gold palette |

Repeat this step for each question Ali asks. Check `done` field — when `true`, move to step 3.

---

#### 3. Check conversation status (optional)

```bash
curl http://localhost:8000/api/conversation/SESSION_ID/status
```

---

#### 4. Start build (after conversation is done)

```bash
curl -X POST http://localhost:8000/api/build/start \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "SESSION_ID",
    "max_iterations": 10,
    "model": "opus"
  }'
```

**Response:** `{"build_id": "...", "status": "started"}`

---

#### 5. Monitor build progress

**Poll status:**
```bash
curl http://localhost:8000/api/build/BUILD_ID/status
```

**Stream progress (SSE):**
```bash
curl -N http://localhost:8000/api/build/BUILD_ID/stream
```

---

### Quick automated test (Python)

```python
"""
Automated backend test — runs the full Telos flow without the frontend.
Usage: cd server && uv run python ../test_backend.py
"""
import httpx
import time

BASE = "http://localhost:8000"

# Predefined answers for the test scenario
ANSWERS = [
    "Women aged 25-45 who are existing customers. We have about 50,000 women in our CRM database.",
    "Modern, elegant, empowering design. Purple and gold color scheme with floral accents. We want to use AI-generated images of diverse women.",
    "We use Mailchimp for email and our website is Next.js on Vercel. The landing page is at /womens-day.",
    "20% discount with code WOMENSDAY2026, valid March 1-15, 2026. The offer applies to all products.",
    "Empowering and celebratory tone. Key message: 'Celebrate the women who inspire us.' Campaign launches March 1st, landing page ready by Feb 28.",
    "Deliverables: updated hero section on landing page with AI image, email blast template with discount CTA and AI image, 3 social media banner variations.",
    "Budget is flexible, around $2000 for the campaign. We have existing brand guidelines in Figma.",
    "We need email open rate tracking, click-through tracking, and conversion tracking for the discount code.",
    "The AI-generated images should be professional, diverse, show empowerment themes. No stock photo look. Artistic, modern illustration style preferred.",
    "We want A/B testing on email subject lines. Subject A: 'You deserve this' Subject B: 'Celebrate with 20% off'",
]

def run_test():
    client = httpx.Client(base_url=BASE, timeout=60)

    # 1. Start conversation
    print("=== Starting conversation ===")
    resp = client.post("/api/conversation/start", json={
        "message": (
            "We need to create a marketing campaign for International Womans Day. "
            "We have to edit the landing page and send out email campaigns to all "
            "the women in our database with a discount. Both the website and email "
            "campaign has to include a relevant AI generated image."
        )
    })
    resp.raise_for_status()
    data = resp.json()
    session_id = data["session_id"]
    print(f"Session: {session_id}")
    print(f"Mission: {data['mission']}")
    print(f"Categories: {data['categories']}")
    print(f"Coverage: {data['initial_coverage']:.0%}")
    print(f"Question: {data.get('first_question', 'N/A')}")
    print(f"Done: {data['done']}")
    print()

    # 2. Answer loop
    answer_idx = 0
    while not data["done"] and answer_idx < len(ANSWERS):
        question = data.get("first_question") or data.get("next_question")
        if not question:
            break

        answer = ANSWERS[answer_idx]
        print(f"--- Turn {answer_idx + 1} ---")
        print(f"Q: {question}")
        print(f"A: {answer[:80]}...")

        resp = client.post(f"/api/conversation/{session_id}/answer", json={
            "answer": answer,
        })
        resp.raise_for_status()
        data = resp.json()
        print(f"Coverage: {data['coverage']:.0%} | Resolved: {data['resolved']} | Done: {data['done']}")
        print()
        answer_idx += 1

    if not data["done"]:
        print("WARNING: Conversation not done after all answers. Check status:")
        resp = client.get(f"/api/conversation/{session_id}/status")
        print(resp.json())
        return

    # 3. Start build
    print("=== Starting build ===")
    resp = client.post("/api/build/start", json={
        "session_id": session_id,
        "max_iterations": 10,
        "model": "opus",
    })
    resp.raise_for_status()
    build_data = resp.json()
    build_id = build_data["build_id"]
    print(f"Build ID: {build_id}")

    # 4. Poll status
    while True:
        time.sleep(5)
        resp = client.get(f"/api/build/{build_id}/status")
        status = resp.json()
        print(f"  Status: {status['status']} | Iteration: {status['iteration']}/{status['total_iterations']}")
        if status["status"] in ("completed", "failed"):
            print(f"  Success: {status.get('success')} | Error: {status.get('error')}")
            break

if __name__ == "__main__":
    run_test()
```

---

### Running the test

```bash
# Terminal 1: Start the backend server
cd server
uv run uvicorn server.main:app --host 0.0.0.0 --port 8000 --reload

# Terminal 2: Run the automated test
cd /Users/valprok/Documents/telos
uv run python test_backend.py

# Or manually via curl (see steps above)
```

### Direct Python test (bypasses HTTP server)

If the server keeps restarting (e.g. `--reload` mode), use the direct test script
which calls the same Python internals without HTTP:

```bash
cd /Users/valprok/Documents/telos
PYTHONPATH="$PWD:$PWD/agent" server/.venv/bin/python test_backend.py
```

This script (`test_backend.py`) directly instantiates `ConversationLoop` and runs
the full interview with predefined answers. It's the most reliable way to test.

### Environment variables required
- `OPENROUTER_API_KEY` — for Gemini context MCP and image generation
- `MISSIONS_PATH` — path to missions.jsonl (defaults to `train/data/missions.jsonl`)

---

## Test Results (2026-02-22)

### Conversation Phase
- **Categories detected**: `web_development`, `email_marketing`, `marketing_campaign`
- **Elements identified**: 45
- **Turns completed**: 10
- **Final coverage**: 72% (27/45 elements answered)
- **C1 source**: `lookup` (keyword fallback — LLM extractor needs `transformers`/`torch`)

### Notes
- The keyword-based extractor resolves ~3 elements per turn. With the LLM extractor
  (`transformers` + `torch` installed), it captures more bonus elements and reaches
  higher coverage faster.
- Ali correctly identified this as a multi-category project spanning web dev, email
  marketing, and marketing campaign — merging elements from all three.
- The generated `context.md` (~14KB) contains structured sections (Project Scope,
  Target Audience, Design & Visuals, Technical Setup, etc.) plus a full conversation log.
