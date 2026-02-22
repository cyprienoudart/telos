"""
Qwen Answer Extractor (Component 4) — Parses user answers and updates elements.
For hackathon: uses keyword matching + heuristic extraction.
For production: would use Alibaba Qwen2.5 for NLU.
"""
from __future__ import annotations

import re


class QwenExtractor:
    """
    Component 4: Processes the user's answer to:
    1. Extract structured facts
    2. Match facts to elements → mark as answered
    3. Provide content for context.md update
    
    Named after the Alibaba Qwen model that would power this in production.
    """

    def extract(self, user_answer: str, targeted_elements: list[str],
                all_elements: list[dict]) -> dict:
        """
        Extract information from a user's answer.

        Args:
            user_answer: The raw text of the user's response
            targeted_elements: Element names this question was targeting
            all_elements: Full element list to check for bonus extractions

        Returns:
            {
                "resolved_elements": {name: value},
                "bonus_elements": {name: value},  # extras not targeted but found
                "summary": str,  # clean prose for context.md
            }
        """
        answer_lower = user_answer.lower().strip()
        resolved = {}
        bonus = {}

        # 1. Resolve targeted elements — the question was about these
        for elem_name in targeted_elements:
            value = self._extract_value_for_element(elem_name, user_answer)
            if value:
                resolved[elem_name] = value

        # If user gave a substantive answer, assume targeted elements are answered
        # even if we can't extract a clean value
        if len(answer_lower) > 10:
            for elem_name in targeted_elements:
                if elem_name not in resolved:
                    resolved[elem_name] = user_answer.strip()

        # 2. Check for bonus extractions — info about non-targeted elements
        for elem in all_elements:
            if elem["name"] in targeted_elements:
                continue
            if elem["status"] == "answered":
                continue
            value = self._extract_value_for_element(elem["name"], user_answer)
            if value:
                bonus[elem["name"]] = value

        # 3. Generate clean summary for context.md
        summary = self._generate_summary(user_answer, resolved, bonus)

        return {
            "resolved_elements": resolved,
            "bonus_elements": bonus,
            "summary": summary,
        }

    def _extract_value_for_element(self, element_name: str, text: str) -> str | None:
        """Try to extract a specific value for an element from text."""
        text_lower = text.lower()

        extractors = {
            "tech_platform": self._extract_platform,
            "existing_platform": self._extract_platform,
            "platform_preference": self._extract_platform,
            "platform": self._extract_app_platform,
            "design_style": self._extract_design,
            "design_direction": self._extract_design,
            "color_preferences": self._extract_colors,
            "existing_branding": self._extract_branding,
            "target_audience": self._extract_audience,
            "target_customers": self._extract_audience,
            "target_market": self._extract_audience,
            "target_users": self._extract_audience,
            "existing_audience_size": self._extract_audience_size,
            "audience_size": self._extract_audience_size,
            "offer_promotion": self._extract_offer,
            "offer_incentive": self._extract_offer,
            "timeline": self._extract_timeline,
            "campaign_dates": self._extract_dates,
            "budget": self._extract_budget,
            "budget_range": self._extract_budget,
            "deliverables": self._extract_deliverables,
            "visual_assets_needed": self._extract_visuals,
            "visual_assets": self._extract_visuals,
        }

        extractor = extractors.get(element_name)
        if extractor:
            return extractor(text, text_lower)
        return None

    def _extract_platform(self, text: str, text_lower: str) -> str | None:
        platforms = [
            "shopify", "wordpress", "woocommerce", "squarespace",
            "wix", "webflow", "custom", "next.js", "react", "vue",
        ]
        found = [p for p in platforms if p in text_lower]
        return ", ".join(found) if found else None

    def _extract_app_platform(self, text: str, text_lower: str) -> str | None:
        platforms = ["ios", "android", "cross-platform", "react native", "flutter"]
        found = [p for p in platforms if p in text_lower]
        return ", ".join(found) if found else None

    def _extract_design(self, text: str, text_lower: str) -> str | None:
        styles = [
            "modern", "minimal", "bold", "elegant", "playful", "clean",
            "professional", "vintage", "futuristic", "illustrated",
            "photo-realistic", "abstract", "artistic",
        ]
        found = [s for s in styles if s in text_lower]
        # Also look for color mentions as part of design
        colors = self._extract_colors(text, text_lower)
        parts = found.copy()
        if colors:
            parts.append(colors)
        return ", ".join(parts) if parts else None

    def _extract_colors(self, text: str, text_lower: str) -> str | None:
        colors = [
            "purple", "violet", "blue", "red", "green", "pink",
            "orange", "yellow", "black", "white", "gold", "silver",
            "pastel", "dark", "bright", "navy", "teal", "coral",
        ]
        found = [c for c in colors if c in text_lower]
        return ", ".join(found) if found else None

    def _extract_branding(self, text: str, text_lower: str) -> str | None:
        has_indicators = [
            "already have", "existing", "current", "we have", "our logo",
            "our brand", "our colors",
        ]
        no_indicators = ["no logo", "don't have", "from scratch", "no branding"]

        for ind in no_indicators:
            if ind in text_lower:
                return "No existing branding — starting fresh"
        for ind in has_indicators:
            if ind in text_lower:
                return "Has existing branding assets"
        return None

    def _extract_audience(self, text: str, text_lower: str) -> str | None:
        # This is usually a free-form answer, extract the full response
        # if it seems to be about audience
        audience_words = [
            "customer", "user", "audience", "people", "women", "men",
            "families", "professional", "business", "local", "global",
            "age", "young", "old", "millenni", "gen z",
        ]
        if any(w in text_lower for w in audience_words):
            # Return a cleaned version
            return text.strip()
        return None

    def _extract_audience_size(self, text: str, text_lower: str) -> str | None:
        match = re.search(r'(\d+[,.]?\d*)\s*[kK]?\s*(?:subscriber|follower|user|customer|email|list|people)', text_lower)
        if match:
            return match.group(0).strip()
        return None

    def _extract_offer(self, text: str, text_lower: str) -> str | None:
        match = re.search(r'(\d+%?\s*(?:off|discount|sale|code|coupon|free|gift))', text_lower)
        if match:
            return match.group(0).strip()
        # Check for explicit mentions
        offer_words = ["discount", "promo", "coupon", "free shipping", "special offer", "deal"]
        for w in offer_words:
            if w in text_lower:
                return text.strip()
        return None

    def _extract_timeline(self, text: str, text_lower: str) -> str | None:
        timeline_patterns = [
            r'\b(\d+\s*(?:day|week|month|year)s?)\b',
            r'\b(asap|urgent|no rush|flexible|end of (?:month|year|week))\b',
            r'\b(march|april|may|june|july|august|september|october|november|december|january|february)\s*\d*\b',
        ]
        for pattern in timeline_patterns:
            match = re.search(pattern, text_lower)
            if match:
                return match.group(0).strip()
        return None

    def _extract_dates(self, text: str, text_lower: str) -> str | None:
        date_patterns = [
            r'\b(march\s*\d+|international women\'?s day|iwday)\b',
            r'\b(valentine|christmas|black friday|new year|easter|halloween)\b',
            r'\b\d{1,2}[/\-]\d{1,2}(?:[/\-]\d{2,4})?\b',
        ]
        for pattern in date_patterns:
            match = re.search(pattern, text_lower)
            if match:
                return match.group(0).strip()
        return None

    def _extract_budget(self, text: str, text_lower: str) -> str | None:
        match = re.search(r'[\$€£]?\s*\d+[,.]?\d*\s*(?:k|K|€|\$|£|euro|dollar|usd|eur)?', text)
        if match:
            return match.group(0).strip()
        budget_words = ["no budget", "flexible", "tight budget", "limited"]
        for w in budget_words:
            if w in text_lower:
                return w
        return None

    def _extract_deliverables(self, text: str, text_lower: str) -> str | None:
        deliverable_words = [
            "website", "email", "landing page", "banner", "image",
            "illustration", "video", "social media", "post", "ad",
            "logo", "flyer", "brochure", "app",
        ]
        found = [w for w in deliverable_words if w in text_lower]
        return ", ".join(found) if found else None

    def _extract_visuals(self, text: str, text_lower: str) -> str | None:
        visual_words = [
            "photo", "illustration", "graphic", "image", "video",
            "banner", "icon", "animation", "ai-generated", "ai image",
        ]
        found = [w for w in visual_words if w in text_lower]
        if found:
            # Try to get a number
            num_match = re.search(r'(\d+)[\s\-]+(?:image|photo|illustration|graphic)', text_lower)
            count = num_match.group(1) if num_match else "several"
            return f"{count} {', '.join(found)}"
        return None

    def _generate_summary(self, answer: str, resolved: dict, bonus: dict) -> str:
        """Generate a clean prose summary for context.md."""
        # Just return the cleaned answer — context_manager handles formatting
        return answer.strip()

    def update_elements(self, elements: list[dict],
                        resolved: dict[str, str],
                        bonus: dict[str, str]) -> list[dict]:
        """Update element list with resolved values."""
        for elem in elements:
            if elem["name"] in resolved:
                elem["status"] = "answered"
                elem["value"] = resolved[elem["name"]]
            elif elem["name"] in bonus:
                elem["status"] = "answered"
                elem["value"] = bonus[elem["name"]]
        return elements
