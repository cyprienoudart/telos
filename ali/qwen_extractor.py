"""
Answer Extractor (Component 4) — Parses user answers and updates elements.

Primary: Uses a fine-tuned GPT-2 + LoRA model for structured extraction.
Fallback: Uses keyword matching + heuristic extraction if LLM unavailable.
"""
from __future__ import annotations

import json
import os
import re
from typing import Optional


class QwenExtractor:
    """
    Component 4: Processes the user's answer to:
    1. Extract structured facts
    2. Match facts to elements → mark as answered
    3. Provide content for context.md update

    Primary path: Fine-tuned GPT-2 + LoRA extractor LLM.
    Fallback path: Regex/keyword extractors (kept for resilience).
    """

    def __init__(self, model_dir: str = "ali/trained_models"):
        """Load the extraction LLM if available."""
        self._llm_model = None
        self._llm_tokenizer = None
        self._llm_device = "cpu"

        self._load_extractor_llm(model_dir)

    @staticmethod
    def _clean_adapter_config(llm_path: str):
        """Strip fields unknown to older PEFT versions from adapter_config.json."""
        config_path = os.path.join(llm_path, "adapter_config.json")
        if not os.path.exists(config_path):
            return
        # Only keep fields that PEFT <=0.14 already knows
        KNOWN_FIELDS = {
            "alpha_pattern", "auto_mapping", "base_model_name_or_path",
            "bias", "fan_in_fan_out", "inference_mode", "init_lora_weights",
            "layer_replication", "layers_pattern", "layers_to_transform",
            "loftq_config", "lora_alpha", "lora_dropout", "megatron_config",
            "megatron_core", "modules_to_save", "peft_type", "r",
            "rank_pattern", "revision", "target_modules", "task_type",
            "use_dora", "use_rslora",
            # Newer but harmless fields
            "corda_config", "eva_config", "exclude_modules",
            "target_parameters", "trainable_token_indices", "use_qalora",
            "lora_bias", "qalora_group_size",
        }
        try:
            with open(config_path, "r") as f:
                cfg = json.load(f)
            unknown = set(cfg.keys()) - KNOWN_FIELDS
            if unknown:
                for key in unknown:
                    del cfg[key]
                with open(config_path, "w") as f:
                    json.dump(cfg, f, indent=2)
        except Exception:
            pass  # Best-effort cleanup

    def _load_extractor_llm(self, model_dir: str):
        """Load the fine-tuned GPT-2 extraction model."""
        llm_path = os.path.join(model_dir, "extractor_llm")
        if not os.path.exists(llm_path):
            return

        try:
            import torch
            from transformers import GPT2LMHeadModel, AutoTokenizer
            from peft import PeftModel

            # Clean adapter config for PEFT version compatibility
            self._clean_adapter_config(llm_path)

            # Detect device
            if torch.backends.mps.is_available():
                self._llm_device = "mps"
            elif torch.cuda.is_available():
                self._llm_device = "cuda"
            else:
                self._llm_device = "cpu"

            # Load base model + LoRA adapter
            base_model = GPT2LMHeadModel.from_pretrained("gpt2")
            self._llm_model = PeftModel.from_pretrained(base_model, llm_path)
            self._llm_model.eval()
            self._llm_model = self._llm_model.to(self._llm_device)

            self._llm_tokenizer = AutoTokenizer.from_pretrained(llm_path)
            if self._llm_tokenizer.pad_token is None:
                self._llm_tokenizer.pad_token = self._llm_tokenizer.eos_token

            # print("   🧠 Loaded fine-tuned extractor LLM (GPT-2 + LoRA)")

        except Exception as e:
            # print(f"   ⚠️ Could not load extractor LLM: {e}")
            self._llm_model = None
            self._llm_tokenizer = None

    @property
    def has_llm(self) -> bool:
        """Check if the extractor LLM is loaded."""
        return self._llm_model is not None

    # ─── Main extraction entry point ─────────────────────────────

    def extract(self, user_answer: str, targeted_elements: list[str],
                all_elements: list[dict]) -> dict:
        """
        Extract information from a user's answer.

        Tries the fine-tuned LLM first, falls back to regex if unavailable.

        Args:
            user_answer: The raw text of the user's response
            targeted_elements: Element names this question was targeting
            all_elements: Full element list to check for bonus extractions

        Returns:
            {
                "resolved_elements": {name: value},
                "bonus_elements": {name: value},
                "summary": str,
                "source": "llm" | "regex",
            }
        """
        # Try LLM extraction first
        if self._llm_model is not None:
            llm_result = self._extract_with_llm(
                user_answer, targeted_elements, all_elements
            )
            if llm_result is not None:
                return llm_result

        # Fallback: regex/keyword extraction
        return self._extract_with_regex(user_answer, targeted_elements, all_elements)

    # ─── LLM extraction path ─────────────────────────────────────

    def _extract_with_llm(self, user_answer: str, targeted_elements: list[str],
                          all_elements: list[dict]) -> Optional[dict]:
        """Use the fine-tuned LLM to extract structured info from the answer."""
        try:
            import torch

            # Build prompt in the same format as training data
            undefined_elements = [
                e for e in all_elements
                if e["status"] == "undefined" and e["name"] not in targeted_elements
            ]

            prompt = self._build_llm_prompt(
                user_answer, targeted_elements, undefined_elements
            )

            # Generate
            inputs = self._llm_tokenizer(
                prompt, return_tensors="pt"
            ).to(self._llm_device)

            with torch.no_grad():
                output = self._llm_model.generate(
                    **inputs,
                    max_new_tokens=100,
                    do_sample=True,
                    temperature=0.5,  # Lower temp for more precise extraction
                    top_p=0.9,
                    repetition_penalty=1.2,
                    pad_token_id=self._llm_tokenizer.eos_token_id,
                )

            generated = self._llm_tokenizer.decode(
                output[0], skip_special_tokens=True
            )

            # Extract the part after [EXTRACT]
            if "[EXTRACT]" in generated:
                extraction_text = generated.split("[EXTRACT]")[-1].strip()
            else:
                extraction_text = generated[len(prompt):].strip()

            # Clean up — take first meaningful line
            extraction_text = extraction_text.split("\n")[0].strip()
            extraction_text = extraction_text.split("[")[0].strip()

            # Parse the structured output
            resolved, bonus = self._parse_llm_output(
                extraction_text, targeted_elements, all_elements
            )

            # If the LLM didn't parse anything but user gave a substantive answer,
            # fall back to regex extraction for targeted + bonus elements.
            # But first, skip non-answers like "I don't know", "not sure", etc.
            if not self._is_non_answer(user_answer):
                if not resolved:
                    # LLM couldn't parse — try regex for targets only
                    for elem_name in targeted_elements:
                        value = self._extract_value_for_element(elem_name, user_answer)
                        if value:
                            resolved[elem_name] = value
                    # If regex also found nothing, assign full answer to targets
                    if not resolved and len(user_answer.strip()) > 20:
                        for elem_name in targeted_elements:
                            resolved[elem_name] = user_answer.strip()
                # Always try bonus extraction via regex
                if not bonus:
                    for elem in all_elements:
                        if elem["name"] in targeted_elements or elem["name"] in resolved:
                            continue
                        if elem["status"] == "answered":
                            continue
                        value = self._extract_value_for_element(elem["name"], user_answer)
                        if value:
                            bonus[elem["name"]] = value

            summary = self._generate_summary(user_answer, resolved, bonus)

            return {
                "resolved_elements": resolved,
                "bonus_elements": bonus,
                "summary": summary,
                "source": "llm",
            }

        except Exception as e:
            # print(f"   ⚠️ LLM extraction failed: {e}")
            return None

    def _build_llm_prompt(self, answer: str, targets: list[str],
                          undefined_elements: list[dict]) -> str:
        """Build the input prompt for the extractor LLM."""
        lines = []
        lines.append(f"[ANSWER] {answer}")

        targets_str = ", ".join(t.replace("_", " ") for t in targets)
        lines.append(f"[TARGETS] {targets_str}")

        if undefined_elements:
            undef_str = ", ".join(
                f"{e['name'].replace('_', ' ')} ({e.get('description', '')[:40]})"
                for e in undefined_elements[:10]
            )
            lines.append(f"[UNDEFINED] {undef_str}")

        lines.append("[EXTRACT]")
        return " ".join(lines)

    def _parse_llm_output(self, extraction_text: str,
                          targeted_elements: list[str],
                          all_elements: list[dict]) -> tuple[dict, dict]:
        """Parse the structured LLM output into resolved and bonus dicts."""
        resolved = {}
        bonus = {}

        # Valid element names for validation
        all_names = {e["name"] for e in all_elements}
        target_set = set(targeted_elements)

        # Expected format: "resolved: elem=value, elem=value | bonus: elem=value"
        parts = extraction_text.split("|")

        for part in parts:
            part = part.strip()

            is_bonus = part.lower().startswith("bonus:")
            is_resolved = part.lower().startswith("resolved:")

            if is_resolved:
                content = part.split(":", 1)[1].strip()
            elif is_bonus:
                content = part.split(":", 1)[1].strip()
            else:
                content = part.strip()

            if content.lower() == "none" or not content:
                continue

            # Parse "elem name=value, elem name=value"
            assignments = self._split_assignments(content)

            for elem_key, value in assignments.items():
                # Convert "elem name" back to "elem_name"
                elem_name = elem_key.strip().replace(" ", "_")

                # Find the closest matching element name
                matched_name = self._match_element_name(elem_name, all_names)
                if not matched_name:
                    continue

                if is_bonus or (matched_name not in target_set and not is_resolved):
                    bonus[matched_name] = value.strip()
                else:
                    resolved[matched_name] = value.strip()

        return resolved, bonus

    def _split_assignments(self, content: str) -> dict[str, str]:
        """Split 'elem=value, elem=value' into a dict, handling commas in values."""
        result = {}

        # Try splitting by comma first, but be careful with values containing commas
        # Pattern: "element name=some value"
        # We look for "word word=..." patterns
        segments = re.split(r',\s*(?=[a-z][a-z ]*=)', content)

        for segment in segments:
            segment = segment.strip()
            if "=" not in segment:
                continue

            key, _, value = segment.partition("=")
            key = key.strip()
            value = value.strip()

            if key and value:
                result[key] = value

        return result

    def _match_element_name(self, candidate: str, valid_names: set[str]) -> Optional[str]:
        """Find the closest matching element name from the valid set."""
        # Exact match
        if candidate in valid_names:
            return candidate

        # Try with underscores
        underscore_version = candidate.replace(" ", "_")
        if underscore_version in valid_names:
            return underscore_version

        # Fuzzy: check if candidate is a substring or contains a valid name
        for name in valid_names:
            name_words = set(name.split("_"))
            candidate_words = set(candidate.split("_"))
            # At least 2 word overlap for longer names, or exact for short ones
            overlap = name_words & candidate_words
            if len(overlap) >= min(2, len(name_words)):
                return name

        return None

    # ─── Regex fallback extraction path ──────────────────────────

    def _extract_with_regex(self, user_answer: str, targeted_elements: list[str],
                            all_elements: list[dict]) -> dict:
        """Regex/keyword extraction — the original fallback method."""
        answer_lower = user_answer.lower().strip()
        resolved = {}
        bonus = {}

        # 1. Resolve targeted elements
        for elem_name in targeted_elements:
            value = self._extract_value_for_element(elem_name, user_answer)
            if value:
                resolved[elem_name] = value

        # If user gave a substantive, non-evasive answer, assign remaining targets
        if not self._is_non_answer(user_answer) and len(answer_lower) > 20:
            for elem_name in targeted_elements:
                if elem_name not in resolved:
                    resolved[elem_name] = user_answer.strip()

        # 2. Check for bonus extractions
        for elem in all_elements:
            if elem["name"] in targeted_elements:
                continue
            if elem["status"] == "answered":
                continue
            value = self._extract_value_for_element(elem["name"], user_answer)
            if value:
                bonus[elem["name"]] = value

        summary = self._generate_summary(user_answer, resolved, bonus)

        return {
            "resolved_elements": resolved,
            "bonus_elements": bonus,
            "summary": summary,
            "source": "regex",
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
                return "No existing branding, starting fresh"
        for ind in has_indicators:
            if ind in text_lower:
                return "Has existing branding assets"
        return None

    def _extract_audience(self, text: str, text_lower: str) -> str | None:
        audience_words = [
            "customer", "user", "audience", "people", "women", "men",
            "families", "professional", "business", "local", "global",
            "age", "young", "old", "millenni", "gen z",
        ]
        if any(w in text_lower for w in audience_words):
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
        offer_words = ["discount", "promo", "coupon", "free shipping", "special offer", "deal"]
        for w in offer_words:
            if w in text_lower:
                return text.strip()
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
            num_match = re.search(r'(\d+)[\s\-]+(?:image|photo|illustration|graphic)', text_lower)
            count = num_match.group(1) if num_match else "several"
            return f"{count} {', '.join(found)}"
        return None

    @staticmethod
    def _is_non_answer(text: str) -> bool:
        """Detect when a user explicitly declines to answer or gives no info."""
        lower = text.lower().strip()
        non_answer_phrases = [
            "not sure", "don't know", "no idea", "i don't know",
            "haven't decided", "haven't thought", "let me think",
            "i'll get back", "skip", "pass", "next question",
            "no preference", "no opinion", "whatever you think",
            "i'm not sure", "im not sure", "idk", "dunno",
            "can't say", "can't decide", "hard to say",
            "not yet", "still thinking", "need to think",
            "maybe later", "come back to this", "i'll decide later",
        ]
        # If the answer is very short AND matches a non-answer pattern
        if len(lower) < 60:
            for phrase in non_answer_phrases:
                if phrase in lower:
                    return True
        return False

    def _generate_summary(self, answer: str, resolved: dict, bonus: dict) -> str:
        """Generate a clean prose summary for context.md."""
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
