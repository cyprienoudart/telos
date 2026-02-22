"""Interview runner — generates follow-up questions from conversation transcripts.

Ali (finetuned model with Python harness) handles the user conversation, then
passes a plain-text transcript to us. We invoke Claude Code in read-only mode
(with Gemini MCP access) to assess the transcript and generate follow-up
questions, or signal that enough context has been gathered.

Legacy API (ask_agent / add_user_answers) is preserved for backwards compat.
"""

import json
from dataclasses import dataclass, field
from pathlib import Path

from telos_agent.claude import invoke_claude
from telos_agent.mcp_config import generate_mcp_config


def _extract_json_object(text: str) -> dict | None:
    """Extract a JSON object from text that may contain prose, code blocks, etc.

    Handles nested braces by using a bracket-counting approach.
    """
    import re

    # Try code block extraction first (```json ... ```)
    block_match = re.search(r'```(?:json)?\s*\n?(\{.*?\})\s*\n?```', text, re.DOTALL)
    if block_match:
        try:
            return json.loads(block_match.group(1))
        except json.JSONDecodeError:
            pass

    # Bracket-counting: find the first '{' and match to its closing '}'
    start = text.find('{')
    if start == -1:
        return None

    depth = 0
    for i in range(start, len(text)):
        if text[i] == '{':
            depth += 1
        elif text[i] == '}':
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(text[start:i + 1])
                except json.JSONDecodeError:
                    return None
    return None


@dataclass
class InterviewResult:
    """Result from a single interview round."""
    questions: list[str]
    ready: bool


@dataclass
class InterviewRound:
    """A single round of interview questions and answers (legacy)."""
    round_num: int
    questions: list[str]
    agent_answers: dict[str, str] = field(default_factory=dict)
    user_answers: dict[str, str] = field(default_factory=dict)


class InterviewRunner:
    """Runs interview rounds where Claude Code explores the codebase to generate questions."""

    # Read-only tools the interview agent is allowed to use
    ALLOWED_TOOLS = ["Read", "Glob", "Grep", "Task", "WebFetch", "WebSearch", "mcp__gemini-context__summarize", "mcp__gemini-context__answer_question"]

    def __init__(
        self,
        project_dir: Path,
        agent_dir: Path | None = None,
        context_dir: Path | None = None,
    ):
        self.project_dir = Path(project_dir).resolve()
        if agent_dir is None:
            self.agent_dir = Path(__file__).resolve().parent.parent
        else:
            self.agent_dir = Path(agent_dir).resolve()
        self.context_dir = Path(context_dir).resolve() if context_dir else None
        self.rounds: list[InterviewRound] = []
        self._latest_transcript: str | None = None

    def process_round(self, transcript: str, no_more_questions: bool = False) -> InterviewResult:
        """Process an interview transcript and generate follow-up questions.

        Ali passes us the full conversation transcript (north star + summary + Q&A).
        We invoke Claude Code with read-only tools + Gemini MCP to assess whether
        enough context has been gathered, and if not, generate follow-up questions.

        Args:
            transcript: Plain-text conversation transcript from Ali.
            no_more_questions: If True, skip question generation and signal ready.
                Two scenarios trigger this flag:
                1. Ali has collected enough answers and signals done — the transcript
                   contains the final round of answers.
                2. The user declines further questions — Ali passes the same (or empty)
                   transcript and forces progression to planning. The current
                   implementation handles both correctly by returning ready=True
                   with no follow-up questions.

        Returns:
            InterviewResult with follow-up questions, or ready=True if done.
        """
        self._latest_transcript = transcript

        if no_more_questions:
            return InterviewResult(questions=[], ready=True)

        # Generate MCP config with Gemini access (no reviewer)
        mcp_config_path = generate_mcp_config(
            agent_dir=self.agent_dir,
            project_dir=self.project_dir,
            context_dir=self.context_dir,
            include_gemini=True,
            include_reviewer=False,
        )

        prompt = self._build_round_prompt(transcript)

        result = invoke_claude(
            prompt=prompt,
            working_dir=self.project_dir,
            allowed_tools=self.ALLOWED_TOOLS,
            mcp_config=mcp_config_path,
            output_format="json",
            model="sonnet",
        )

        return self._parse_round_result(result.stdout)

    def get_context(self) -> str | list[dict]:
        """Return the interview context for plan/PRD generation.

        If process_round() was used, returns the latest transcript string.
        If legacy ask_agent() was used, returns the structured transcript list.
        """
        if self._latest_transcript is not None:
            return self._latest_transcript
        # Legacy path
        transcript = []
        for r in self.rounds:
            entry = {
                "round": r.round_num,
                "questions": r.questions,
                "agent_answers": r.agent_answers,
                "user_answers": r.user_answers,
            }
            transcript.append(entry)
        return transcript

    # --- Legacy API (deprecated, kept for backwards compat) ---

    def ask_agent(self, questions: list[str], round_num: int | None = None) -> dict[str, str]:
        """Ask Claude Code to answer questions by reading the codebase.

        Deprecated: Use process_round() instead.
        """
        if round_num is None:
            round_num = len(self.rounds) + 1

        prompt = self._build_agent_prompt(questions)
        result = invoke_claude(
            prompt=prompt,
            working_dir=self.project_dir,
            allowed_tools=["Read", "Glob", "Grep", "Task", "WebFetch", "WebSearch"],
            output_format="json",
            model="sonnet",
        )

        answers = self._parse_answers(result.stdout, questions)

        interview_round = InterviewRound(
            round_num=round_num,
            questions=questions,
            agent_answers=answers,
        )
        self.rounds.append(interview_round)

        return answers

    def add_user_answers(self, round_num: int, answers: dict[str, str]) -> None:
        """Store user answers for a given round. Deprecated: Use process_round() instead."""
        for r in self.rounds:
            if r.round_num == round_num:
                r.user_answers = answers
                return
        raise ValueError(f"No interview round {round_num} found")

    # --- Prompt building ---

    def _build_round_prompt(self, transcript: str) -> str:
        return (
            "You are an interview assistant assessing whether enough context has been "
            "gathered to plan a software project. You have access to the codebase (read-only) "
            "and the Gemini context MCP for additional project information.\n\n"
            "## Conversation Transcript\n\n"
            f"{transcript}\n\n"
            "## Your Task\n\n"
            "1. Read the transcript carefully to understand the project goals and context gathered so far.\n"
            "2. Explore the codebase and query Gemini context if helpful.\n"
            "3. Decide: is there enough information to create a solid project plan, or are there gaps?\n"
            "4. If gaps exist, generate 2-5 targeted follow-up questions.\n"
            "5. If sufficient context exists, signal readiness.\n\n"
            "## Readiness Guidance\n\n"
            "Scale your thoroughness to the project's complexity:\n"
            "- **Simple projects** (static sites, landing pages, small CRUD apps): 5-7 Q&A pairs "
            "covering core features, user needs, and key constraints is usually sufficient.\n"
            "- **Complex projects** (platforms, multi-service architectures, data pipelines): more depth is warranted.\n"
            "- Don't ask about cosmetic details, implementation choices, or operational concerns "
            "that can be reasonably defaulted during planning.\n"
            "- Only generate follow-up questions for decisions that would **fundamentally change "
            "the architecture** or that the planning agent cannot reasonably assume.\n"
            "- When in doubt, lean toward ready=true. The planning phase handles unknowns gracefully.\n\n"
            "## Output Format\n\n"
            "Respond with a JSON object:\n"
            '- If more questions needed: {"ready": false, "questions": ["q1", "q2", ...]}\n'
            '- If ready: {"ready": true, "questions": []}\n'
        )

    def _build_agent_prompt(self, questions: list[str]) -> str:
        """Build prompt for legacy ask_agent()."""
        numbered = "\n".join(f"{i+1}. {q}" for i, q in enumerate(questions))
        return (
            "You are answering interview questions about this codebase. "
            "Explore the project thoroughly using the available tools, then "
            "answer each question based on what you find.\n\n"
            "Questions:\n"
            f"{numbered}\n\n"
            "Respond with a JSON object mapping each question number (as string) "
            'to your answer. Example: {"1": "answer1", "2": "answer2"}'
        )

    # --- Parsing ---

    def _parse_round_result(self, output: str) -> InterviewResult:
        """Parse Claude's output into an InterviewResult.

        Handles three layers of wrapping:
        1. Raw JSON from the model
        2. Claude CLI envelope: {"type":"result","result":"...model text..."}
        3. Model text containing explanation + embedded JSON code block
        """
        text = output

        # Layer 1: Unwrap Claude CLI JSON envelope
        try:
            envelope = json.loads(output)
            if isinstance(envelope, dict) and "result" in envelope:
                text = envelope["result"]
                # Try direct parse of the result field
                try:
                    data = json.loads(text) if isinstance(text, str) else text
                    if isinstance(data, dict) and "ready" in data:
                        return InterviewResult(
                            questions=data.get("questions", []),
                            ready=data.get("ready", False),
                        )
                except (json.JSONDecodeError, ValueError):
                    pass  # Fall through to extract from text
        except (json.JSONDecodeError, ValueError):
            pass  # Not JSON envelope, treat as raw text

        # Layer 2: Extract JSON object from text (handles code blocks, explanation text)
        data = _extract_json_object(text)
        if data and isinstance(data, dict):
            return InterviewResult(
                questions=data.get("questions", []),
                ready=data.get("ready", False),
            )

        return InterviewResult(questions=[], ready=False)

    def _parse_answers(self, output: str, questions: list[str]) -> dict[str, str]:
        """Parse agent output into question->answer mapping (legacy)."""
        text = output

        # Unwrap Claude CLI envelope
        try:
            envelope = json.loads(output)
            if isinstance(envelope, dict) and "result" in envelope:
                text = envelope["result"] if isinstance(envelope["result"], str) else str(envelope["result"])
            elif isinstance(envelope, dict):
                return {questions[int(k)-1]: v for k, v in envelope.items() if k.isdigit()}
        except (json.JSONDecodeError, ValueError):
            pass

        # Try to extract JSON from text
        data = _extract_json_object(text)
        if data and isinstance(data, dict):
            try:
                return {questions[int(k)-1]: v for k, v in data.items() if k.isdigit()}
            except (IndexError, ValueError):
                pass

        return {q: text for q in questions}
