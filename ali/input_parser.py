"""
Input Parser (Step 0) — Parses user's initial text and attached files.
Extracts the mission statement and identifies any already-answered elements.
Supports multi-task detection (e.g., "website update + email marketing").
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Optional


class InputParser:
    """
    Step 0: Always start here.
    Parses the user's initial input to extract:
    1. The mission (what do they want?)
    2. Category(ies) — supports detecting MULTIPLE tasks
    3. Any elements already answered from their text or files
    """

    # Keywords that hint at mission categories
    CATEGORY_HINTS = {
        "web_development": [
            "website", "web app", "landing page", "homepage", "site",
            "redesign", "web page", "web platform", "website update",
            "update my site", "update my website", "new website",
        ],
        "marketing_campaign": [
            "campaign", "marketing", "email blast", "newsletter",
            "social media campaign", "ad campaign", "promotion",
            "marketing push", "ads campaign",
        ],
        "design_branding": [
            "logo", "brand", "branding", "identity", "design system",
            "rebrand", "visual identity", "brand identity",
        ],
        "content_creation": [
            "blog", "content strategy", "article", "copywriting",
            "content plan", "content calendar", "blog posts",
        ],
        "ecommerce": [
            "online store", "shop", "e-commerce", "ecommerce", "sell online",
            "product catalog", "marketplace", "shopify store",
        ],
        "mobile_app": [
            "mobile app", "ios app", "android app", "application",
            "native app", "cross-platform app", "phone app",
        ],
        "data_analytics": [
            "dashboard", "analytics", "data visualization", "report",
            "metrics", "kpi", "data dashboard", "business intelligence",
        ],
        "event_campaign": [
            "event", "launch event", "international", "celebration",
            "themed", "seasonal", "holiday", "women's day",
            "themed campaign", "seasonal campaign",
        ],
        "saas_product": [
            "saas", "software as a service", "subscription platform",
            "web platform", "software product", "saas product",
            "cloud service", "platform for",
        ],
        "social_media": [
            "social media strategy", "social media", "instagram",
            "tiktok", "social presence", "social content",
            "social media plan", "grow on social",
        ],
        "api_backend": [
            "api", "backend", "rest api", "microservice",
            "backend service", "server", "endpoint",
        ],
        "video_production": [
            "video", "video production", "promo video", "explainer video",
            "tutorial video", "brand video", "commercial",
        ],
        "email_marketing": [
            "email marketing", "newsletter", "email campaign",
            "drip campaign", "email automation", "email list",
            "mailing list", "email sequence", "email setup",
        ],
        "chatbot_ai": [
            "chatbot", "ai assistant", "chat bot", "customer service bot",
            "ai chatbot", "virtual assistant", "conversational ai",
        ],
        "ux_redesign": [
            "ux", "user experience", "ux redesign", "usability",
            "ux audit", "ui/ux", "user interface",
        ],
    }

    # Patterns that extract specific element values from text
    ELEMENT_EXTRACTORS = {
        "tech_platform": [
            r"\b(shopify|wordpress|woocommerce|squarespace|wix|webflow|"
            r"custom|react|next\.?js|vue|angular)\b"
        ],
        "existing_platform": [
            r"\b(shopify|wordpress|woocommerce|squarespace|wix|webflow)\b"
        ],
        "platform_preference": [
            r"\b(shopify|wordpress|woocommerce|squarespace|wix|webflow)\b"
        ],
        "platform": [
            r"\b(ios|android|cross-platform|react native|flutter)\b"
        ],
        "design_style": [
            r"(?:theme|style|look|aesthetic|vibe)[:\s]+([^.!?]+)",
            r"\b(modern|minimal|bold|elegant|playful|professional|"
            r"vintage|futuristic|clean)\b"
        ],
        "design_direction": [
            r"(?:theme|style|look|aesthetic|vibe)[:\s]+([^.!?]+)",
        ],
        "color_preferences": [
            r"\b(purple|violet|blue|red|green|pink|orange|yellow|"
            r"black|white|gold|silver|pastel|dark|bright)\b.*?"
            r"(?:theme|color|palette|scheme)?"
        ],
        "existing_branding": [
            r"(?:already have|existing|current)\s+(?:a\s+)?(?:logo|brand|colors?)",
        ],
        "target_audience": [
            r"(?:targeting|target audience[:\s]+|aimed at|designed for|customers? (?:are|is))([^.!?]+)",
        ],
        "event_theme": [
            r"\b(international women'?s day|iwday|valentine|christmas|"
            r"black friday|new year|easter|halloween|women'?s day)\b"
        ],
        "campaign_dates": [
            r"\b(international women'?s day|iwday|march 8|valentine|"
            r"christmas|black friday|new year|easter|halloween)\b"
        ],
        "existing_audience_size": [
            r"(\d+[kK]?)\s*(?:subscribers?|followers?|users?|customers?)"
        ],
        "offer_incentive": [
            r"(\d+%?\s*(?:off|discount|sale|promotion|coupon|code))"
        ],
    }

    def __init__(self, missions_path: str = "train/data/missions.jsonl"):
        self.missions = self._load_missions(missions_path)

    def _load_missions(self, path: str) -> list[dict]:
        """Load mission definitions from missions.jsonl."""
        missions = []
        missions_file = Path(path)
        if missions_file.exists():
            with open(missions_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        missions.append(json.loads(line))
        return missions

    def parse(self, user_text: str, attached_files: Optional[list[str]] = None) -> dict:
        """
        Parse user input and return structured result.
        Supports detecting multiple task categories.

        Returns:
            {
                "mission": str,
                "category": str,           # primary category
                "categories": [str],        # all detected categories
                "elements": [...],
                "pre_answered": {element_name: extracted_value, ...},
                "raw_text": str
            }
        """
        # Combine all text sources
        full_text = user_text
        if attached_files:
            for file_path in attached_files:
                fp = Path(file_path)
                if fp.exists() and fp.suffix in (".md", ".txt", ".text"):
                    full_text += "\n\n" + fp.read_text(encoding="utf-8")

        # 1. Identify mission categories (supports multiple)
        categories = self._detect_multiple_categories(full_text)
        primary_category = categories[0] if categories else "web_development"

        # 2. Get element checklist (merged from all categories)
        elements = self._get_elements_for_categories(categories)

        # 3. Extract already-answered elements from the text
        pre_answered = self._extract_known_elements(full_text)

        # 4. Extract the mission statement
        mission = self._extract_mission(full_text)

        return {
            "mission": mission,
            "category": primary_category,
            "categories": categories,
            "elements": elements,
            "pre_answered": pre_answered,
            "raw_text": full_text,
        }

    def _detect_multiple_categories(self, text: str) -> list[str]:
        """Detect all relevant mission categories from the text.
        Returns sorted by confidence score, highest first.
        Multi-word keyword matches get higher weight."""
        text_lower = text.lower()
        scores = {}
        for category, keywords in self.CATEGORY_HINTS.items():
            score = 0
            for kw in keywords:
                if kw in text_lower:
                    word_count = len(kw.split())
                    score += word_count * 2 if word_count > 1 else 1
            if score > 0:
                scores[category] = score

        if not scores:
            return ["web_development"]

        # Sort by score descending
        sorted_cats = sorted(scores.keys(), key=lambda c: scores[c], reverse=True)

        # Return all categories with score >= 2, or at least the top one
        threshold = 2
        detected = [c for c in sorted_cats if scores[c] >= threshold]
        if not detected:
            detected = [sorted_cats[0]]

        return detected

    def _detect_category(self, text: str) -> str:
        """Detect the most likely mission category from the text.
        Kept for backward compatibility."""
        categories = self._detect_multiple_categories(text)
        return categories[0]

    def _get_elements_for_categories(self, categories: list[str]) -> list[dict]:
        """Get merged element checklist from multiple categories.
        Deduplicates by element name, keeping the highest score."""
        seen = {}  # name -> element dict

        for category in categories:
            for mission in self.missions:
                if mission["category"] == category:
                    for elem in mission["elements"]:
                        name = elem["name"]
                        new_elem = {**elem, "status": "undefined", "category": category}
                        if name not in seen or elem["score"] > seen[name]["score"]:
                            seen[name] = new_elem
                    break

        if not seen:
            # Fallback to first mission
            if self.missions:
                return [
                    {**elem, "status": "undefined", "category": self.missions[0]["category"]}
                    for elem in self.missions[0]["elements"]
                ]
            return []

        # Sort by score descending
        elements = sorted(seen.values(), key=lambda e: e["score"], reverse=True)
        return elements

    def _get_elements_for_category(self, category: str) -> list[dict]:
        """Get the element checklist for a single category (backward compat)."""
        return self._get_elements_for_categories([category])

    def _extract_known_elements(self, text: str) -> dict[str, str]:
        """Extract any element values already present in the user's text."""
        known = {}
        text_lower = text.lower()

        for element_name, patterns in self.ELEMENT_EXTRACTORS.items():
            for pattern in patterns:
                match = re.search(pattern, text_lower, re.IGNORECASE)
                if match:
                    value = match.group(1) if match.lastindex else match.group(0)
                    known[element_name] = value.strip()
                    break

        return known

    def _extract_mission(self, text: str) -> str:
        """Extract a clean mission statement from the user's text."""
        patterns = [
            r"(?:i want to|i'd like to|i need to|we want to|we need to|"
            r"i'm looking to|we're looking to)\s+(.+?)(?:\.|$)",
            r"(?:build|create|make|design|develop|launch|run)\s+(.+?)(?:\.|$)",
        ]

        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(0).strip().rstrip(".")

        # Fallback: use the first sentence
        first_sentence = text.split(".")[0].strip()
        return first_sentence if len(first_sentence) < 200 else first_sentence[:200]
