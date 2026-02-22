"""Pydantic request/response schemas for the Telos API."""

from __future__ import annotations

from pydantic import BaseModel, Field


# ── Conversation ──────────────────────────────────────────────────────────

class ConversationStartRequest(BaseModel):
    message: str = Field(..., min_length=1, description="User's initial project description")
    context_dir: str | None = Field(None, description="Path to context files for RAG pre-answering")
    github_url: str | None = Field(None, description="GitHub repo URL to clone as project context")


class ConversationStartResponse(BaseModel):
    session_id: str
    mission: str
    categories: list[str]
    pre_answered_count: int
    rag_answered_count: int
    total_elements: int
    initial_coverage: float
    first_question: str | None
    done: bool
    repo_url: str | None = None
    repo_dir: str | None = None


class ConversationAnswerRequest(BaseModel):
    answer: str = Field(..., min_length=1, description="User's answer to the current question")


class ConversationAnswerResponse(BaseModel):
    resolved: list[str]
    bonus: list[str]
    coverage: float
    next_question: str | None
    done: bool
    turn: int


class ConversationStatusResponse(BaseModel):
    turn: int
    coverage: float
    coverage_pct: str
    answered_count: int
    undefined_count: int
    total_elements: int
    done: bool
    categories: list[str]


# ── Build ─────────────────────────────────────────────────────────────────

class BuildStartRequest(BaseModel):
    session_id: str = Field(..., description="Session ID from completed conversation")
    context_dir: str | None = Field(None, description="Path to context files for Gemini MCP")
    max_iterations: int = Field(10, ge=1, le=50)
    model: str = Field("opus")


class DebugBuildStartRequest(BaseModel):
    """Skip Ali interview — use a pre-baked fixture file to start the build."""
    fixture_path: str | None = Field(None, description="Path to context fixture (defaults to test/fixtures/debug_context.md)")
    project_dir: str | None = Field(None, description="Build target directory (defaults to /tmp/telos-debug-build)")
    context_dir: str | None = Field(None, description="Context dir for Gemini MCP")
    max_iterations: int = Field(10, ge=1, le=50)
    model: str = Field("opus")


class BuildConfirmRequest(BaseModel):
    model: str = Field("opus")
    max_iterations: int = Field(10, ge=1, le=50)


class BuildEstimateRequest(BaseModel):
    model: str = Field("opus")
    max_iterations: int = Field(10, ge=1, le=50)


class BuildStartResponse(BaseModel):
    build_id: str
    status: str  # "started"


class PhaseEstimateSchema(BaseModel):
    phase: str
    input_tokens: int
    output_tokens: int
    model: str
    cost_usd: float


class CostEstimateResponse(BaseModel):
    low_usd: float
    typical_usd: float
    high_usd: float
    model: str
    max_iterations: int
    estimated_prd_count: int
    breakdown: list[PhaseEstimateSchema]


class BuildStatusResponse(BaseModel):
    build_id: str
    status: str  # "running", "completed", "failed"
    build_phase: str  # "planning", "planned", "executing"
    iteration: int
    total_iterations: int
    success: bool | None = None
    error: str | None = None


# ── PRD Progress ─────────────────────────────────────────────────────────

class PrdCheckboxItem(BaseModel):
    text: str
    checked: bool


class PrdProgress(BaseModel):
    filename: str       # "01-setup.md"
    title: str          # first H1, or filename stem
    items: list[PrdCheckboxItem]
    total: int
    done: int
    percent: float      # 0.0–100.0


class PrdProgressResponse(BaseModel):
    build_id: str
    prds: list[PrdProgress]
    total_items: int
    total_done: int
    overall_percent: float
