"""
SFT Element Model (Component 1) — Identifies task elements and importance scores.
Uses the training data from missions.jsonl as the knowledge base.

Primary: Uses a fine-tuned GPT-2+LoRA LLM to identify category + elements.
Fallback: Lookup mode (pattern matching to training data) when LLM unavailable.
"""
from __future__ import annotations

import json
import re
from pathlib import Path


class SFTElementModel:
    """
    Component 1: Given a mission, output the list of elements + importance scores.

    Primary: Fine-tuned GPT-2+LoRA identifies category + elements from text.
    Fallback: Lookup mode matches mission to closest category in missions.jsonl.
    """

    def __init__(self, missions_path: str = "train/data/missions.jsonl"):
        self.missions = self._load_missions(missions_path)
        self.c1_llm_path = "ali/trained_models/c1_llm"
        self.llm_tokenizer, self.llm_model = self._load_c1_llm()
        self.has_llm = self.llm_model is not None

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

    @staticmethod
    def _clean_adapter_config(llm_path: str):
        """Strip fields unknown to older PEFT versions from adapter_config.json."""
        config_path = Path(llm_path) / "adapter_config.json"
        if not config_path.exists():
            return
        KNOWN_FIELDS = {
            "alpha_pattern", "auto_mapping", "base_model_name_or_path",
            "bias", "fan_in_fan_out", "inference_mode", "init_lora_weights",
            "layer_replication", "layers_pattern", "layers_to_transform",
            "loftq_config", "lora_alpha", "lora_dropout", "megatron_config",
            "megatron_core", "modules_to_save", "peft_type", "r",
            "rank_pattern", "revision", "target_modules", "task_type",
            "use_dora", "use_rslora",
            "corda_config", "eva_config", "exclude_modules",
            "target_parameters", "trainable_token_indices", "use_qalora",
            "lora_bias", "qalora_group_size",
        }
        try:
            cfg = json.loads(config_path.read_text())
            unknown = set(cfg.keys()) - KNOWN_FIELDS
            if unknown:
                for key in unknown:
                    del cfg[key]
                config_path.write_text(json.dumps(cfg, indent=2))
        except Exception:
            pass

    def _load_c1_llm(self):
        """Load the fine-tuned C1 LLM (GPT-2 + LoRA adapter)."""
        try:
            from transformers import AutoTokenizer, AutoModelForCausalLM
            from peft import PeftModel

            model_path = Path(self.c1_llm_path)
            if not model_path.exists():
                # print("   ℹ️  C1 LLM not found — using lookup fallback")
                return None, None

            # Clean adapter config for PEFT version compatibility
            self._clean_adapter_config(self.c1_llm_path)

            tokenizer = AutoTokenizer.from_pretrained(self.c1_llm_path)
            if tokenizer.pad_token is None:
                tokenizer.pad_token = tokenizer.eos_token

            base_model = AutoModelForCausalLM.from_pretrained("gpt2")
            model = PeftModel.from_pretrained(base_model, self.c1_llm_path)
            model.eval()

            # print("   🧠 Loaded fine-tuned C1 LLM (GPT-2 + LoRA)")
            return tokenizer, model
        except Exception:
            return None, None

    def identify_from_text(self, user_text: str,
                           pre_answered: dict[str, str] = None) -> tuple[list[str], list[dict]] | None:
        """
        Use the C1 LLM to identify category + elements from user text.

        Returns:
            (categories, elements) if LLM succeeds, None if it fails.
            - categories: list of detected category strings
            - elements: list of element dicts with name, score, description, status, value
        """
        if not self.has_llm:
            return None

        try:
            import torch
            device = "mps" if torch.backends.mps.is_available() else "cpu"
            self.llm_model = self.llm_model.to(device)

            prompt = f"[MISSION] {user_text} [IDENTIFY]"
            inputs = self.llm_tokenizer(prompt, return_tensors="pt").to(device)

            with torch.no_grad():
                output = self.llm_model.generate(
                    **inputs,
                    max_new_tokens=250,
                    do_sample=True,
                    temperature=0.7,
                    top_p=0.9,
                    repetition_penalty=1.2,
                    pad_token_id=self.llm_tokenizer.eos_token_id,
                )

            generated = self.llm_tokenizer.decode(output[0], skip_special_tokens=True)

            # Extract the part after [IDENTIFY]
            if "[IDENTIFY]" in generated:
                result_text = generated.split("[IDENTIFY]")[-1].strip()
            else:
                result_text = generated[len(prompt):].strip()

            # Clean up — take first line, stop at next token marker
            result_text = result_text.split("\n")[0].strip()
            result_text = result_text.split("[")[0].strip()

            if not result_text:
                return None

            # Parse: "category: <cat> | elements: name=score, name=score, ..."
            parsed = self._parse_llm_output(result_text, pre_answered)
            if parsed:
                return parsed

        except Exception as e:
            # print(f"   ⚠️  C1 LLM inference failed: {e}")
            pass

        return None

    def _parse_llm_output(self, text: str,
                          pre_answered: dict[str, str] = None) -> tuple[list[str], list[dict]] | None:
        """Parse the LLM output into categories and elements."""
        pre_answered = pre_answered or {}

        # Split on "|" to get category part and elements part
        parts = text.split("|")
        if len(parts) < 2:
            return None

        # Parse category
        cat_part = parts[0].strip()
        cat_match = re.match(r"category:\s*(.+)", cat_part, re.IGNORECASE)
        if not cat_match:
            return None

        cat_str = cat_match.group(1).strip()
        categories = [c.strip() for c in cat_str.split(",") if c.strip()]

        # Validate categories against known missions
        known_cats = {m["category"] for m in self.missions}
        valid_categories = [c for c in categories if c in known_cats]
        if not valid_categories:
            # Try fuzzy match — the LLM might use slightly different names
            for cat in categories:
                cat_clean = cat.replace(" ", "_").lower()
                for known in known_cats:
                    if cat_clean in known or known in cat_clean:
                        valid_categories.append(known)
                        break
        if not valid_categories:
            return None

        # Parse elements
        elem_part = "|".join(parts[1:]).strip()
        elem_match = re.match(r"elements:\s*(.+)", elem_part, re.IGNORECASE)
        if not elem_match:
            return None

        # Build known element names for fuzzy matching
        known_elements = {}  # name -> {score, description}
        for cat in valid_categories:
            for mission in self.missions:
                if mission["category"] == cat:
                    for e in mission["elements"]:
                        known_elements[e["name"]] = e

        elem_str = elem_match.group(1).strip()
        elements = []
        seen_names = set()

        # Extract name=score pairs — flexible regex to handle LLM noise
        for m in re.finditer(r"([a-zA-Z_][a-zA-Z0-9_]*)\s*=\s*(-?\d+)", elem_str):
            raw_name = m.group(1)
            score = max(0, int(m.group(2)))

            # Try to match to a known element name
            name = self._fuzzy_match_element(raw_name, known_elements)
            if name and name not in seen_names:
                seen_names.add(name)
                known = known_elements.get(name)
                description = known["description"] if known else name.replace("_", " ").title()
                # Use the known score if available (more reliable)
                final_score = known["score"] if known else score

                element = {
                    "name": name,
                    "score": final_score,
                    "description": description,
                    "status": "undefined",
                    "value": None,
                }

                # Check if pre-answered
                for answered_name, answered_value in pre_answered.items():
                    if (answered_name == name or
                            answered_name in name or
                            name in answered_name):
                        element["status"] = "answered"
                        element["value"] = answered_value
                        break

                elements.append(element)

        # If we got fewer than 5 elements from parsing, supplement with known
        # elements not yet included (the LLM identified the category correctly)
        if len(elements) < 5 and known_elements:
            for ename, edata in known_elements.items():
                if ename not in seen_names:
                    element = {
                        "name": ename,
                        "score": edata["score"],
                        "description": edata["description"],
                        "status": "undefined",
                        "value": None,
                    }
                    for answered_name, answered_value in pre_answered.items():
                        if (answered_name == ename or
                                answered_name in ename or
                                ename in answered_name):
                            element["status"] = "answered"
                            element["value"] = answered_value
                            break
                    elements.append(element)
                    seen_names.add(ename)

        if not elements:
            return None

        # Sort by score descending
        elements.sort(key=lambda e: e["score"], reverse=True)

        return valid_categories, elements

    def _fuzzy_match_element(self, raw_name: str,
                              known_elements: dict) -> str | None:
        """Fuzzy-match an LLM-generated element name to a known element."""
        # Direct match
        if raw_name in known_elements:
            return raw_name

        # Normalize: lowercase, underscores
        normalized = raw_name.lower().replace(" ", "_")
        if normalized in known_elements:
            return normalized

        # Try removing double underscores
        normalized = re.sub(r"_+", "_", normalized).strip("_")
        if normalized in known_elements:
            return normalized

        # Substring matching — check if any known element is a close match
        for known in known_elements:
            # "targetusers" → "target_users"
            known_flat = known.replace("_", "")
            norm_flat = normalized.replace("_", "")
            if known_flat == norm_flat:
                return known
            # One contains the other (e.g., "contenttypes" matches "content_type")
            if len(norm_flat) >= 5 and (norm_flat in known_flat or known_flat in norm_flat):
                return known

        return None

    def _get_element_description(self, elem_name: str,
                                  categories: list[str]) -> str:
        """Look up an element's description from missions.jsonl."""
        for cat in categories:
            for mission in self.missions:
                if mission["category"] == cat:
                    for elem in mission["elements"]:
                        if elem["name"] == elem_name:
                            return elem["description"]
        # Fallback: search all missions
        for mission in self.missions:
            for elem in mission["elements"]:
                if elem["name"] == elem_name:
                    return elem["description"]
        # Last resort: humanize the name
        return elem_name.replace("_", " ").title()

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
