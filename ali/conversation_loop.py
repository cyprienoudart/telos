"""
Conversation Loop — Orchestrates the full TELOS conversation flow.
Runs: Step 0 → C1 → C2 → (C3 ↔ C4 loop) until ≥90% coverage.
Supports multi-task detection and Q&A logging.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional

from ali.input_parser import InputParser
from ali.sft_element_model import SFTElementModel
from ali.clustering import ElementClusterer
from ali.rl_question_generator import RLQuestionGenerator
from ali.qwen_extractor import QwenExtractor
from ali.context_manager import ContextManager


class ConversationLoop:
    """
    Main orchestrator that chains all 4 components together.

    Flow:
    1. Parse user input (Step 0) — supports multiple tasks
    2. Identify elements (C1: SFT) — merged from all detected categories
    3. Cluster elements (C2: K-Means)
    4. Loop: generate question (C3: RL) → get answer → extract (C4: Qwen)
    5. Stop at ≥90% coverage or max turns
    6. Write final context.md for Opus (with Q&A log)
    """

    MAX_TURNS = 10
    COVERAGE_THRESHOLD = 0.90

    def __init__(self, missions_path: str = "training_data/missions.jsonl",
                 context_path: str = "context.md"):
        self.parser = InputParser(missions_path=missions_path)
        self.sft_model = SFTElementModel(missions_path=missions_path)
        self.clusterer = ElementClusterer()
        self.question_gen = RLQuestionGenerator()
        self.extractor = QwenExtractor()
        self.context_mgr = ContextManager(context_path=context_path)

        self.elements: list[dict] = []
        self.clusters: list[dict] = []
        self.conversation_history: list[dict] = []
        self.turn_count = 0
        self.categories: list[str] = []

    def start(self, user_text: str, attached_files: Optional[list[str]] = None) -> dict:
        """
        Initialize the conversation from the user's first input.
        Supports multi-task: detects multiple categories and merges elements.

        Returns:
            {
                "mission": str,
                "category": str,
                "categories": [str],
                "pre_answered_count": int,
                "total_elements": int,
                "initial_coverage": float,
                "first_question": str | None,
                "done": bool,
            }
        """
        # Step 0: Parse user input (supports multi-task)
        parsed = self.parser.parse(user_text, attached_files)
        self.categories = parsed.get("categories", [parsed["category"]])

        # C1: Identify elements with pre-filled answers (merged from all categories)
        self.elements = self.sft_model.identify_elements_multi(
            categories=self.categories,
            pre_answered=parsed["pre_answered"],
        )

        # C2: Cluster elements
        self.clusters = self.clusterer.cluster(self.elements)

        # Create initial context.md
        known_info = {}
        unknown_elements = []
        for elem in self.elements:
            if elem["status"] == "answered":
                section = self._element_to_section_name(elem["name"])
                if section not in known_info:
                    known_info[section] = ""
                known_info[section] += f"{elem['value']}\n"
            else:
                unknown_elements.append(elem["description"])

        self.context_mgr.create_initial(
            mission=parsed["mission"],
            known_info=known_info,
            unknown_elements=unknown_elements,
        )

        # Check if we already have enough
        coverage = self.sft_model.get_coverage(self.elements)
        pre_answered = len([e for e in self.elements if e["status"] == "answered"])

        result = {
            "mission": parsed["mission"],
            "category": parsed["category"],
            "categories": self.categories,
            "pre_answered_count": pre_answered,
            "total_elements": len(self.elements),
            "initial_coverage": coverage,
            "first_question": None,
            "done": coverage >= self.COVERAGE_THRESHOLD,
        }

        # Generate first question if not done
        if not result["done"]:
            candidates = self.question_gen.generate_candidates(
                self.elements, self.clusters, self.conversation_history
            )
            best = self.question_gen.select_best(candidates)
            if best:
                result["first_question"] = best["question"]
                result["_question_info"] = best
                result["_candidates"] = candidates

        return result

    def process_answer(self, user_answer: str, question_info: dict = None) -> dict:
        """
        Process a user's answer and generate the next question.

        Args:
            user_answer: What the user said
            question_info: The question that was asked (with targets)

        Returns:
            {
                "resolved": [element_names],
                "bonus": [element_names],
                "coverage": float,
                "next_question": str | None,
                "done": bool,
                "turn": int,
            }
        """
        self.turn_count += 1
        targets = question_info.get("targets", []) if question_info else []
        question_text = question_info.get("question", "") if question_info else ""

        # Record Q&A in context manager
        if question_text:
            self.context_mgr.add_qa_turn(question_text, user_answer)

        # C4: Extract facts from answer
        extraction = self.extractor.extract(
            user_answer=user_answer,
            targeted_elements=targets,
            all_elements=self.elements,
        )

        # Update elements
        self.elements = self.extractor.update_elements(
            self.elements,
            extraction["resolved_elements"],
            extraction["bonus_elements"],
        )

        # Update context.md
        resolved_names = list(extraction["resolved_elements"].keys())
        bonus_names = list(extraction["bonus_elements"].keys())
        all_resolved = resolved_names + bonus_names

        # Build section content from resolved elements
        for elem_name in all_resolved:
            section = self._element_to_section_name(elem_name)
            value = (extraction["resolved_elements"].get(elem_name) or
                     extraction["bonus_elements"].get(elem_name, ""))
            existing = self.context_mgr.known_info.get(section, "")
            if value not in existing:
                self.context_mgr.known_info[section] = (existing + "\n" + value).strip()

        # Update unknown elements
        self.context_mgr.unknown_elements = [
            e["description"] for e in self.elements if e["status"] == "undefined"
        ]
        self.context_mgr._write()

        # Record in conversation history
        self.conversation_history.append({
            "turn": self.turn_count,
            "question": question_text,
            "answer": user_answer,
            "targets": targets,
            "resolved": all_resolved,
        })

        # Recalculate coverage
        coverage = self.sft_model.get_coverage(self.elements)

        # Re-cluster with updated elements
        self.clusters = self.clusterer.cluster(self.elements)

        # Check stopping conditions
        done = (
            coverage >= self.COVERAGE_THRESHOLD
            or self.turn_count >= self.MAX_TURNS
            or not self.sft_model.get_undefined_elements(self.elements)
        )

        result = {
            "resolved": all_resolved,
            "bonus": bonus_names,
            "coverage": coverage,
            "next_question": None,
            "done": done,
            "turn": self.turn_count,
        }

        # Generate next question if not done
        if not done:
            candidates = self.question_gen.generate_candidates(
                self.elements, self.clusters, self.conversation_history
            )
            best = self.question_gen.select_best(candidates)
            if best:
                result["next_question"] = best["question"]
                result["_question_info"] = best
                result["_candidates"] = candidates
            else:
                result["done"] = True

        return result

    def _element_to_section_name(self, element_name: str) -> str:
        """Map element names to clean section names for context.md."""
        section_map = {
            # Design & Brand
            "design_style": "Design & Visuals",
            "design_direction": "Design & Visuals",
            "existing_branding": "Design & Visuals",
            "color_preferences": "Design & Visuals",
            "visual_assets_needed": "Design & Visuals",
            "visual_assets": "Design & Visuals",
            "style_references": "Design & Visuals",
            "typography_preferences": "Design & Visuals",
            "visual_style": "Design & Visuals",
            "design_template": "Design & Visuals",

            # Audience
            "target_audience": "Target Audience",
            "target_customers": "Target Audience",
            "target_market": "Target Audience",
            "target_users": "Target Audience",
            "existing_audience_size": "Target Audience",
            "audience_size": "Target Audience",
            "target_subscribers": "Target Audience",

            # Content & Messaging
            "key_message": "Content & Messaging",
            "messaging_tone": "Content & Messaging",
            "content_ready": "Content & Messaging",
            "brand_tone": "Content & Messaging",
            "brand_voice": "Content & Messaging",
            "brand_personality": "Content & Messaging",
            "seo_requirements": "Content & Messaging",
            "seo_keywords": "Content & Messaging",
            "content_strategy": "Content & Messaging",
            "content_type": "Content & Messaging",
            "topics_themes": "Content & Messaging",

            # Technical
            "tech_platform": "Technical Setup",
            "existing_platform": "Technical Setup",
            "platform_preference": "Technical Setup",
            "platform": "Technical Setup",
            "domain_hosting": "Technical Setup",
            "integrations": "Technical Setup",
            "tech_stack": "Technical Setup",
            "existing_backend": "Technical Setup",
            "data_sources": "Technical Setup",
            "email_platform": "Technical Setup",

            # Scope
            "main_content_purpose": "Project Scope",
            "pages_structure": "Project Scope",
            "core_features": "Project Scope",
            "deliverables": "Project Scope",
            "campaign_channels": "Project Scope",
            "promotion_channel": "Project Scope",
            "app_purpose": "Project Scope",
            "event_theme": "Project Scope",
            "campaign_goal": "Project Scope",
            "campaign_objectives": "Project Scope",
            "products_services": "Project Scope",
            "product_catalog_size": "Project Scope",
            "email_types": "Project Scope",
            "email_goals": "Project Scope",
            "automation_flows": "Project Scope",

            # Logistics
            "timeline": "Timeline & Budget",
            "campaign_dates": "Timeline & Budget",
            "campaign_duration": "Timeline & Budget",
            "budget": "Timeline & Budget",
            "budget_range": "Timeline & Budget",
            "sending_frequency": "Timeline & Budget",

            # Offer & Commerce
            "offer_promotion": "Offer & Promotion",
            "offer_incentive": "Offer & Promotion",
            "pricing_strategy": "Offer & Promotion",
            "pricing_model": "Offer & Promotion",
            "payment_methods": "Offer & Promotion",
            "shipping_logistics": "Offer & Promotion",
        }
        return section_map.get(element_name, "Additional Details")

    def get_status(self) -> dict:
        """Get current conversation status."""
        coverage = self.sft_model.get_coverage(self.elements)
        undefined = self.sft_model.get_undefined_elements(self.elements)
        answered = [e for e in self.elements if e["status"] == "answered"]
        return {
            "turn": self.turn_count,
            "coverage": coverage,
            "coverage_pct": f"{coverage * 100:.0f}%",
            "answered_count": len(answered),
            "undefined_count": len(undefined),
            "total_elements": len(self.elements),
            "done": coverage >= self.COVERAGE_THRESHOLD,
            "categories": self.categories,
        }
