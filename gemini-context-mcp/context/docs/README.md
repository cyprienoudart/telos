# Project Telos — Context Store

This directory contains the reference documentation and codebase for **Project Telos**,
an internal platform for managing asynchronous research workflows.

## What's Here

| Path | Description |
|------|-------------|
| `docs/team.md` | Team members, roles, and contact info |
| `docs/priorities.md` | Current sprint priorities and roadmap |
| `docs/architecture.pdf` | *(drop your architecture diagram PDF here)* |
| `docs/whiteboard.jpg` | *(drop your whiteboard photo here)* |
| `codebase/src/main.py` | Application entry point |
| `codebase/src/auth/handler.py` | Authentication and session management |
| `codebase/src/models/user.py` | User data model |

## Quick Facts

- **Stack**: Python 3.13, FastAPI, PostgreSQL, Redis
- **Deploy**: Docker Compose → Kubernetes (production)
- **CI**: GitHub Actions → staging on every PR merge
- **Secrets**: All secrets in `.env` (never committed); prod secrets in Vault

## How to Run Locally

```bash
cp .env.example .env        # fill in DB_URL, REDIS_URL, SECRET_KEY
docker compose up -d db redis
pip install -r requirements.txt
uvicorn main:app --reload
```

## Notes for the AI Agent

Drop sample files into `docs/` to test multimodal capabilities:
- A PDF (`architecture.pdf`) to test PDF reading
- A JPEG or PNG (`whiteboard.jpg`) to test image understanding
