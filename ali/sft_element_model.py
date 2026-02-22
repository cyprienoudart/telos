"""
SFT Element Model (Component 1) — Identifies task elements and importance scores.
Uses the training data from missions.jsonl as the knowledge base.
For hackathon: runs in lookup mode (pattern matching to training data).
For production: would be a fine-tuned Qwen2.5 model.
"""
from __future__ import annotations

import json
from pathlib import Path


class SFTElementModel:
    """
    Component 1: Given a mission, output the list of elements + importance scores.

    In lookup mode (hackathon): matches mission to closest category in missions.jsonl.
    In model mode (production): fine-tuned Qwen2.5 predicts elements.
    """

    def __init__(self, missions_path: str = "training_data/missions.jsonl"):
        self.missions = self._load_missions(missions_path)

    def _load_missions(self, path: str) -> list[dict]:
        """Load mission definitions."""
        missions = []
        missions_file = Path(path)
        if missions_file.exists():
            with open(missions_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        missions.append(json.loads(line))
        return missions

    def identify_elements(self, category: str,
                          pre_answered: dict[str, str] = None) -> list[dict]:
        """
        Get element checklist for a mission category.
        Pre-fills status for already-answered elements.
        """
        return self.identify_elements_multi([category], pre_answered)

    def identify_elements_multi(self, categories: list[str],
                                pre_answered: dict[str, str] = None) -> list[dict]:
        """
        Get merged element checklist for multiple mission categories.
        Pre-fills status for already-answered elements.
        Deduplicates by element name, keeping the highest score.

        Args:
            categories: List of mission categories
            pre_answered: Dict of {element_name: value} already known

        Returns:
            List of elements with name, score, description, status, and value
        """
        pre_answered = pre_answered or {}
        seen = {}  # name -> element dict

        for category in categories:
            mission_data = None
            for m in self.missions:
                if m["category"] == category:
                    mission_data = m
                    break

            if not mission_data:
                continue

            for elem in mission_data["elements"]:
                name = elem["name"]
                if name not in seen or elem["score"] > seen[name]["score"]:
                    element = {
                        "name": name,
                        "score": elem["score"],
                        "description": elem["description"],
                        "status": "undefined",
                        "value": None,
                    }

                    # Check if this element was pre-answered
                    for answered_name, answered_value in pre_answered.items():
                        if (answered_name == name or
                                answered_name in name or
                                name in answered_name):
                            element["status"] = "answered"
                            element["value"] = answered_value
                            break

                    seen[name] = element

        if not seen:
            # Fallback: use first mission
            if self.missions:
                mission_data = self.missions[0]
                for elem in mission_data["elements"]:
                    element = {
                        "name": elem["name"],
                        "score": elem["score"],
                        "description": elem["description"],
                        "status": "undefined",
                        "value": None,
                    }
                    for answered_name, answered_value in pre_answered.items():
                        if (answered_name == elem["name"] or
                                answered_name in elem["name"] or
                                elem["name"] in answered_name):
                            element["status"] = "answered"
                            element["value"] = answered_value
                            break
                    seen[elem["name"]] = element

        # Sort by score descending
        elements = sorted(seen.values(), key=lambda e: e["score"], reverse=True)
        return elements

    def get_total_score(self, elements: list[dict]) -> int:
        """Get the total possible score for all elements."""
        return sum(e["score"] for e in elements)

    def get_answered_score(self, elements: list[dict]) -> int:
        """Get the total score of answered elements."""
        return sum(e["score"] for e in elements if e["status"] == "answered")

    def get_coverage(self, elements: list[dict]) -> float:
        """Calculate coverage percentage (0.0 to 1.0)."""
        total = self.get_total_score(elements)
        if total == 0:
            return 1.0
        return self.get_answered_score(elements) / total

    def get_undefined_elements(self, elements: list[dict]) -> list[dict]:
        """Get all undefined elements, sorted by score (highest first)."""
        undefined = [e for e in elements if e["status"] == "undefined"]
        undefined.sort(key=lambda e: e["score"], reverse=True)
        return undefined
