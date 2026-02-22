"""Pydantic request/response schemas for the Telos API."""

from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field


# ── Conversation ──────────────────────────────────────────────────────────

class ConversationStartRequest(BaseModel):
    message: str = Field(..., min_length=1, description="User's initial project description")
    context_dir: Optional[str] = Field(None, description="Path to context files for RAG pre-answering")
    additional_context: Optional[str] = Field(None, description="Gemini-extracted text from uploaded files")
    github_url: Optional[str] = Field(None, description="GitHub repository URL provided by the user")
    files_dir: Optional[str] = Field(None, description="Temp dir with uploaded files to copy into session")


class ConversationStartResponse(BaseModel):
    session_id: str
    mission: str
    categories: List[str]
    pre_answered_count: int
    rag_answered_count: int
    total_elements: int
    initial_coverage: float
    first_question: Optional[str]
    done: bool


class ConversationAnswerRequest(BaseModel):
    answer: str = Field(..., min_length=1, description="User's answer to the current question")


class ConversationAnswerResponse(BaseModel):
    resolved: List[str]
    bonus: List[str]
    coverage: float
    next_question: Optional[str]
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
    categories: List[str]


# ── Build ─────────────────────────────────────────────────────────────────

class BuildStartRequest(BaseModel):
    session_id: str = Field(..., description="Session ID from completed conversation")
    project_dir: str = Field(..., description="Target directory for the built project")
    context_dir: Optional[str] = Field(None, description="Path to context files for Gemini MCP")
    max_iterations: int = Field(10, ge=1, le=50)
    model: str = Field("opus")


class BuildStartResponse(BaseModel):
    build_id: str
    status: str  # "started"


class BuildStatusResponse(BaseModel):
    build_id: str
    status: str  # "running", "completed", "failed"
    iteration: int
    total_iterations: int
    success: Optional[bool] = None
    error: Optional[str] = None
