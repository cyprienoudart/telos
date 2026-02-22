"""
Context Manager — Reads, writes, and updates context.md files.
Keeps context clean (no scores, no technical markers) for Opus consumption.
Includes Q&A conversation log at the end.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Optional


class ContextManager:
    """Manages the context.md file — the single source of truth for the mission."""

    def __init__(self, context_path: str = "context.md"):
        self.context_path = Path(context_path)
        self.mission = ""
        self.source_material = ""
        self.known_info: dict[str, str] = {}  # section_name -> content
        self.unknown_elements: list[str] = []
        self.conversation_log: list[dict] = []  # {"question": str, "answer": str}

    def load(self) -> str:
        """Load existing context.md if it exists."""
        if self.context_path.exists():
            content = self.context_path.read_text(encoding="utf-8")
            self._parse_context(content)
            return content
        return ""

    def _parse_context(self, content: str):
        """Parse an existing context.md into structured data."""
        sections = re.split(r'\n## ', content)
        for section in sections:
            if section.startswith("Mission"):
                self.mission = section.split("\n", 1)[-1].strip()
            elif section.startswith("Source Material"):
                self.source_material = section.split("\n", 1)[-1].strip()
            elif section.startswith("What We Know"):
                self._parse_known_sections(section)
            elif section.startswith("What We Still Need"):
                lines = section.strip().split("\n")[1:]
                self.unknown_elements = [
                    line.strip("- ").strip() for line in lines if line.strip().startswith("-")
                ]

    def _parse_known_sections(self, section_text: str):
        """Parse the 'What We Know' section into sub-sections."""
        subsections = re.split(r'\n### ', section_text)
        for sub in subsections[1:]:  # skip the header
            lines = sub.strip().split("\n")
            title = lines[0].strip()
            content = "\n".join(lines[1:]).strip()
            self.known_info[title] = content

    def create_initial(self, mission: str, source_material: str = "",
                       known_info: Optional[dict[str, str]] = None,
                       unknown_elements: Optional[list[str]] = None):
        """Create the initial context.md from parsed user input."""
        self.mission = mission
        self.source_material = source_material
        self.known_info = known_info or {}
        self.unknown_elements = unknown_elements or []
        self.conversation_log = []
        self._write()

    def update_from_answer(self, section_name: str, content: str,
                           resolved_elements: Optional[list[str]] = None):
        """Update context.md with new information from a user answer."""
        self.known_info[section_name] = content

        # Remove resolved elements from unknown list
        if resolved_elements:
            self.unknown_elements = [
                e for e in self.unknown_elements
                if e not in resolved_elements
            ]
        self._write()

    def add_qa_turn(self, question: str, answer: str):
        """Record a Q&A exchange in the conversation log."""
        self.conversation_log.append({
            "question": question,
            "answer": answer,
        })

    def get_coverage_summary(self) -> dict:
        """Return a summary of what's known vs unknown."""
        return {
            "mission": self.mission,
            "known_sections": list(self.known_info.keys()),
            "known_count": len(self.known_info),
            "unknown_count": len(self.unknown_elements),
            "unknown_elements": self.unknown_elements,
        }

    def _write(self):
        """Write the context.md file in clean prose format."""
        lines = ["# Project Brief", ""]

        # Mission
        lines.append("## Mission")
        lines.append(self.mission)
        lines.append("")

        # Source material (if any)
        if self.source_material:
            lines.append("## Source Material")
            lines.append(self.source_material)
            lines.append("")

        # What we know
        if self.known_info:
            lines.append("## What We Know")
            lines.append("")
            for section_name, content in self.known_info.items():
                lines.append(f"### {section_name}")
                lines.append(content)
                lines.append("")

        # What we still need
        if self.unknown_elements:
            lines.append("## What We Still Need")
            for element in self.unknown_elements:
                lines.append(f"- {element}")
            lines.append("")

        # Conversation log (Q&A at the end)
        if self.conversation_log:
            lines.append("## Conversation Log")
            lines.append("")
            for i, turn in enumerate(self.conversation_log, 1):
                lines.append(f"**Q{i}:** {turn['question']}")
                lines.append(f"**A{i}:** {turn['answer']}")
                lines.append("")

        self.context_path.write_text("\n".join(lines), encoding="utf-8")

    def to_prompt(self) -> str:
        """Return the context as a string suitable for an LLM prompt."""
        if self.context_path.exists():
            return self.context_path.read_text(encoding="utf-8")
        return f"Mission: {self.mission}\nNo additional context available."
