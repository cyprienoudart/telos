<<<<<<< Updated upstream
# telos
Hackeurope project
Devpost: https://devpost.com/software/telos-w9emdy


=======
<p align="center">
  <img src="front/public/Telos logo-Photoroom.png" alt="Telos" width="320" />
</p>

<h3 align="center">From Intent to Execution — Autonomously.</h3>

<p align="center">
  <em>Telos is an AI-native platform that converts a single natural-language instruction into a fully built, tested, and delivered digital project — no technical skill required.</em>
</p>

<p align="center">
  <a href="#quickstart">Quickstart</a> •
  <a href="#how-it-works">How It Works</a> •
  <a href="#architecture">Architecture</a> •
  <a href="#demo">Live Demo</a> •
  <a href="#tech-stack">Tech Stack</a>
</p>

---

## The Problem

Turning an idea into a real product still takes weeks, five different tools, and a project manager.  
Non-technical founders, small businesses, and solo creators are locked out — not because their ideas lack value, but because the execution gap is too wide.

## The Telos Solution

**One conversation. Full project. Delivered.**

We at Telos believe in true agency, today productivity gain through AI is roughly 15%, that's not agency, you spend your day at your desk telling your AI what to do. 

We believe in 100% of your time saved, in true agency, we believe in Telos.
You talk with Telos for 10 minutes as you would with a consultant, a freelancer; and Telos works from A to Z, doesn't compromise your data. Pure IP, transparency and performance.

Tell Telos what you want in plain English (or speak to it). Our AI interview agent asks the right follow-up questions, maps your intent to a structured plan, breaks it into bite-sized PRDs, then deploys a swarm of specialized AI agents to build & review it,  iteratively — until it's done.

> 💬 *"I want a bakery website with an online ordering form and a blog for recipes."*  
> → **6 minutes later:** a deployed website with ordering, CMS-powered blog, responsive design, and SEO — reviewed, tested, and ready.

---

## ✨ Key Features

| | Feature | Description |
|---|---------|-------------|
| 🧠 | **ALI — Adaptive Language Interviewer** | Custom-trained GPT-2+LoRA models that intelligently extract project requirements through conversation. 5-component ML pipeline: element identification, semantic clustering, RL-optimized question selection, and structured answer extraction. |
| 🔄 | **Ralph — Self-Healing Build Loop** | Iterative execution engine that builds, reviews, and fixes its own work. Denial-streak escalation rewrites strategy after repeated failures. Runs until the reviewer approves or budget is exhausted. |
| 🎙️ | **Voice-First UX** | Speak your idea. Real-time voice orb with 4 animated states (idle, listening, thinking, speaking). Canvas-rendered geometric animations that react to audio amplitude. |
| 🤖 | **Multi-Agent Orchestration** | Specialized agents (coder, designer, CRM, marketer) coordinate through MCP tools. Each agent gets scoped permissions, file tools, and a Gemini-powered knowledge base. |
| 📊 | **Coverage-Driven Intelligence** | Dynamic thresholds scale with project complexity. Simple landing page? 85% coverage in 6 questions. Enterprise SaaS? 95% coverage across 15 turns. RAG pre-answers fill gaps automatically. |
| 📦 | **Real Deliverables** | Not mockups — actual HTML/CSS, personalized emails, campaign assets, and CRM integrations. Everything lands in a project directory you own. |

---

## How It Works

```
┌──────────────────────────────────────────────────────────┐
│                      USER INTENT                         │
│               "Build me a bakery website"                │
└──────────────┬───────────────────────────────────────────┘
               │
               ▼
┌──────────────────────────┐
│   🗣️ ALI Interview Agent │    ← 5-component ML pipeline
│   - Parses intent        │     (InputParser → SFT → Clustering
│   - Asks smart follow-ups│     → RL Question Gen → Extractor)
│   - Hits 90%+ coverage   │
└──────────────┬───────────┘
               │ transcript
               ▼
┌──────────────────────────┐
│   📋 Plan Generator      │  ← Claude + Gemini MCP
│   - Architecture         │    context-aware planning
│   - Tech stack           │
│   - Risk analysis        │
└──────────────┬───────────┘
               │ plan.md
               ▼
┌──────────────────────────┐
│   📝 PRD Splitter        │  ← 8-15 checkboxes per PRD
│   - Ordered work units   │    self-contained specs
│   - Acceptance criteria  │
└──────────────┬───────────┘
               │ prds/01-xxx.md, 02-xxx.md, ...
               ▼
┌──────────────────────────┐
│   🔄 Ralph Build Loop    │  ← Builds → Reviews → Fixes
│   - Multi-agent execution│    until approved or max
│   - Self-healing retries │    iterations reached
│   - Verdict-based gating │
└──────────────┬───────────┘
               │
               ▼
┌──────────────────────────┐
│   ✅ Delivered Project   │  ← Real files, not mockups
│   - Website / App        │
│   - Emails & Campaigns   │
│   - CRM Integrations     │
└──────────────────────────┘
```

---

## Architecture

```
telos/
├── ali/                    # 🧠 Adaptive Language Interviewer (custom ML)
│   ├── conversation_loop.py    # Main orchestrator: Step0→C1→C2→C3↔C4
│   ├── input_parser.py         # Multi-task intent detection + pre-extraction
│   ├── sft_element_model.py    # GPT-2+LoRA element identification (C1)
│   ├── clustering.py           # Semantic element clustering (C2)
│   ├── rl_question_generator.py# PPO-scored question generation (C3)
│   ├── qwen_extractor.py       # Structured answer extraction (C4)
│   └── context_manager.py      # context.md lifecycle management
│
├── agent/                  # 🤖 Multi-Agent Orchestration Engine
│   └── telos_agent/
│       ├── orchestrator.py     # interview → plan → PRDs → execute
│       ├── ralph.py            # Self-healing iterative build loop
│       ├── interview.py        # Transcript-based follow-up generation
│       ├── claude.py           # Claude CLI subprocess wrapper
│       ├── cli.py              # Full CLI: interview, plan, build, run
│       ├── mcp/                # MCP tool servers (Gemini context RAG)
│       └── tools/              # Image gen, CRM seeding, email rendering
│
├── server/                 # ⚡ FastAPI Backend
│   └── server/
│       ├── main.py             # App + CORS + lifespan singletons
│       ├── models.py           # Pydantic request/response schemas
│       ├── routes/             # /api/conversation + /api/build (SSE)
│       └── services/           # SessionStore, BuildRunner, RAG bridge
│
├── front/                  # 🎨 Next.js Frontend
│   └── src/
│       ├── components/         # VoiceOrb, ChatContext, Sidebar, MicButton
│       └── app/                # Layout, page routing, globals.css
│
├── train/                  # 🏋️ Training Pipeline
│   ├── train_extended.py       # 7-phase training (evo optimization, Monte Carlo)
│   ├── generate_*_sft.py       # SFT data generators for C1, C3, C4
│   ├── generate_rl_episodes.py # RL episode simulation
│   └── data/                   # 6.6MB of generated training data
│
└── demo/                   # 🎯 Live Demo Output
    ├── plan.md                 # Auto-generated project plan
    ├── prds/                   # 4 auto-generated PRDs
    └── emails/                 # 4 personalized HTML emails (real output)
```

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| **ML Models** | GPT-2 + LoRA (PEFT), SFT + PPO reward shaping |
| **Agent Runtime** | Claude Code CLI, MCP protocol |
| **RAG** | ChromaDB + FastEmbed embeddings |
| **Backend** | FastAPI, Pydantic v2, SSE (EventSource) |
| **Frontend** | Next.js 15, React 19, Canvas API |
| **Voice** | ElevenLabs STT (Scribe) + TTS streaming |
| **Image Gen** | OpenRouter → Gemini Pro Image Preview |
| **CRM** | Twenty CRM (MCP + REST) |

---

## Quickstart

### Prerequisites

- Python 3.11+
- Node.js 18+
- Claude Code CLI installed
- API keys: `OPENROUTER_API_KEY`, `ANTHROPIC_API_KEY`

### 1. Backend

```bash
# Install dependencies
cd server
pip install -e .

# Set environment variables
cp ../agent/.env.example .env
# Edit .env with your API keys

# Run the server
python -m server.main
```

### 2. Frontend

```bash
cd front
npm install
npm run dev
```

### 3. Agent CLI (standalone mode)

```bash
cd agent
pip install -e .

# Full workflow: interview → plan → PRDs → build
telos-agent run --project-dir ./my-project --transcript interview.txt
```

---

## Demo

The `demo/` folder contains **real output** from a Telos run:

- **Input:** *"International Women's Day campaign with landing page, CRM emails, and social assets"*
- **Output:**
  - `plan.md` — Full project plan with architecture, tech stack, risks
  - `prds/` — 4 ordered PRDs with acceptance criteria
  - `emails/` — 4 personalized HTML emails (1.6MB each, with embedded images)
  - `site/` — Updated landing page with IWD campaign section

---

## Training

Telos includes a full ML training pipeline for the ALI model:

```bash
cd train

# Quick training (~5 min)
python train.py

# Extended training with evolutionary optimization (~20 min)
python train_extended.py
```

The pipeline runs 7 phases:
1. **Massive data generation** — Thousands of simulated conversations
2. **Evolutionary reward weight optimization** — Genetic algorithm over PPO weights
3. **Question template evaluation** — Coverage/turn ratio scoring
4. **Multi-pass clustering optimization** — Optimal element groupings
5. **Monte Carlo strategy evaluation** — 500+ simulated conversations
6. **Extended template bank building** — Best performers archived
7. **Final validation** — End-to-end verification

---

## Team

Built with ❤️ at the hackathon.

---

## License

MIT
>>>>>>> Stashed changes
