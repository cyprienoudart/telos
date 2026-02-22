"""Unit tests for interview.py — JSON parsing layers and InterviewResult.

Tests the Bug 2 regression (nested JSON extraction) and all parsing paths.
No Claude API calls — all invoke_claude calls are mocked.
"""

import json
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from telos_agent.interview import (
    InterviewResult,
    InterviewRunner,
    _extract_json_object,
)


class TestExtractJsonObject:
    """Tests for _extract_json_object() helper."""

    def test_extract_json_from_code_block(self):
        """JSON wrapped in ```json``` blocks."""
        text = 'Here is the result:\n```json\n{"ready": true, "questions": []}\n```\nDone.'
        result = _extract_json_object(text)
        assert result == {"ready": True, "questions": []}

    def test_extract_json_nested_braces(self):
        """Handles nested braces in values: {"questions": ["What about {X}?"]}."""
        text = '{"questions": ["What about {braces}?"], "ready": false}'
        result = _extract_json_object(text)
        assert result is not None
        assert result["questions"] == ["What about {braces}?"]
        assert result["ready"] is False

    def test_extract_json_no_json(self):
        """Plain text with no JSON returns None."""
        result = _extract_json_object("Just some text with no JSON at all.")
        assert result is None

    def test_extract_json_malformed(self):
        """Truncated JSON returns None."""
        result = _extract_json_object('{"ready": true, "questions": [')
        assert result is None


class TestParseRoundResult:
    """Tests for InterviewRunner._parse_round_result()."""

    def setup_method(self):
        self.runner = InterviewRunner.__new__(InterviewRunner)

    def test_parse_round_result_direct(self):
        """Raw JSON string → InterviewResult."""
        output = '{"ready": false, "questions": ["What framework?"]}'
        result = self.runner._parse_round_result(output)
        assert isinstance(result, InterviewResult)
        assert result.ready is False
        assert result.questions == ["What framework?"]

    def test_parse_round_result_cli_envelope(self):
        """Claude CLI envelope: {"type":"result","result":"..."}."""
        inner = json.dumps({"ready": True, "questions": []})
        envelope = json.dumps({"type": "result", "result": inner})
        result = self.runner._parse_round_result(envelope)
        assert result.ready is True
        assert result.questions == []

    def test_parse_round_result_envelope_with_prose(self):
        """Envelope where result field contains explanation + code block."""
        inner_text = (
            "Based on my analysis, I believe we have enough context.\n\n"
            '```json\n{"ready": true, "questions": []}\n```\n'
        )
        envelope = json.dumps({"type": "result", "result": inner_text})
        result = self.runner._parse_round_result(envelope)
        assert result.ready is True
        assert result.questions == []

    def test_parse_round_result_unparseable(self):
        """No JSON at all → safe fallback (ready=False, no questions)."""
        result = self.runner._parse_round_result("Claude just rambled without any JSON")
        assert isinstance(result, InterviewResult)
        assert result.ready is False
        assert result.questions == []


class TestParseAnswersLegacy:
    """Tests for legacy _parse_answers()."""

    def setup_method(self):
        self.runner = InterviewRunner.__new__(InterviewRunner)

    def test_parse_answers_legacy(self):
        """Legacy question-answer parsing from numbered JSON."""
        questions = ["What is the stack?", "What is the DB?"]
        output = '{"1": "React + Node", "2": "PostgreSQL"}'
        answers = self.runner._parse_answers(output, questions)
        assert answers["What is the stack?"] == "React + Node"
        assert answers["What is the DB?"] == "PostgreSQL"


class TestInterviewResult:
    """Tests for InterviewResult dataclass."""

    def test_interview_result_dataclass(self):
        """Fields accessible, correct types."""
        r = InterviewResult(questions=["Q1", "Q2"], ready=False)
        assert r.questions == ["Q1", "Q2"]
        assert r.ready is False
        assert isinstance(r.questions, list)
        assert isinstance(r.ready, bool)


class TestInterviewRunner:
    """Tests for InterviewRunner behavior."""

    def test_force_ready_skips_claude(self, tmp_path: Path):
        """no_more_questions=True doesn't invoke Claude."""
        runner = InterviewRunner(project_dir=tmp_path)

        with patch("telos_agent.interview.invoke_claude") as mock_invoke:
            result = runner.process_round("some transcript", no_more_questions=True)

        mock_invoke.assert_not_called()
        assert result.ready is True
        assert result.questions == []
        assert runner.get_context() == "some transcript"
