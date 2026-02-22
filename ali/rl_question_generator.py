"""
RL Question Generator (Component 3) — Generates candidate questions and selects the best.

Uses a fine-tuned GPT-2 LLM (with LoRA) to generate context-aware questions.
Falls back to expert templates if the LLM is not available.
Scores candidates using PPO reward logic with trained weights.
"""
from __future__ import annotations

import json
import os
import random
from typing import Optional


class RLQuestionGenerator:
    """
    Component 3: Generate N candidate questions, score them, pick the best.

    Primary: Uses a fine-tuned GPT-2 model to generate questions based on context.
    Fallback: Uses expert-crafted template bank if the LLM is not available.

    The reward function favors questions that:
    - Target high-importance undefined elements
    - Cover multiple elements in one question (cluster questions)
    - Are specific and natural-sounding
    - Don't re-ask already-answered elements
    """

    def __init__(self, model_dir: str = "ali/trained_models"):
        """Load trained LLM, templates, and weights."""
        self._llm_model = None
        self._llm_tokenizer = None
        self._llm_device = "cpu"
        self._trained_templates = None
        self._reward_weights = None

        # Try loading fine-tuned question LLM
        self._load_question_llm(model_dir)

        # Try loading trained question templates (fallback)
        templates_path = os.path.join(model_dir, "question_templates.json")
        if os.path.exists(templates_path):
            with open(templates_path, "r") as f:
                self._trained_templates = json.load(f)

        # Try loading trained reward weights
        weights_path = os.path.join(model_dir, "reward_weights.json")
        if os.path.exists(weights_path):
            with open(weights_path, "r") as f:
                self._reward_weights = json.load(f)

    def _load_question_llm(self, model_dir: str):
        """Load the fine-tuned GPT-2 question-generation model."""
        llm_path = os.path.join(model_dir, "question_llm")
        if not os.path.exists(llm_path):
            return

        try:
            import torch
            from transformers import GPT2LMHeadModel, GPT2Tokenizer
            from peft import PeftModel

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

            self._llm_tokenizer = GPT2Tokenizer.from_pretrained(llm_path)
            if self._llm_tokenizer.pad_token is None:
                self._llm_tokenizer.pad_token = self._llm_tokenizer.eos_token

            print("   🧠 Loaded fine-tuned question LLM (GPT-2 + LoRA)")

        except Exception as e:
            print(f"   ⚠️ Could not load question LLM: {e}")
            self._llm_model = None
            self._llm_tokenizer = None

    def _generate_llm_question(self, mission_task: str,
                                known_elements: list[dict],
                                unknown_elements: list[dict],
                                conversation_history: list[dict] = None) -> Optional[str]:
        """Use the fine-tuned LLM to generate a question."""
        if self._llm_model is None:
            return None

        try:
            import torch

            # Build the prompt in the same format as training data
            lines = []
            lines.append(f"[MISSION] {mission_task}")

            if known_elements:
                known_str = ", ".join(
                    e["name"].replace("_", " ") for e in known_elements[:5]
                )
                lines.append(f"[KNOWN] {known_str}")
            else:
                lines.append("[KNOWN] nothing yet")

            if unknown_elements:
                unknown_str = ", ".join(
                    f"{e['name'].replace('_', ' ')} ({e['score']})"
                    for e in unknown_elements[:8]
                )
                lines.append(f"[UNKNOWN] {unknown_str}")

            if conversation_history:
                for i, turn in enumerate(conversation_history[-3:], 1):
                    q = turn.get("question", "")
                    if q:
                        lines.append(f"[Q{i}] {q}")

            lines.append("[QUESTION]")
            prompt = " ".join(lines)

            # Generate
            inputs = self._llm_tokenizer(
                prompt, return_tensors="pt"
            ).to(self._llm_device)

            with torch.no_grad():
                output = self._llm_model.generate(
                    **inputs,
                    max_new_tokens=60,
                    do_sample=True,
                    temperature=0.7,
                    top_p=0.9,
                    repetition_penalty=1.2,
                    pad_token_id=self._llm_tokenizer.eos_token_id,
                )

            generated = self._llm_tokenizer.decode(
                output[0], skip_special_tokens=True
            )

            # Extract the question part (after [QUESTION])
            if "[QUESTION]" in generated:
                question = generated.split("[QUESTION]")[-1].strip()
            else:
                question = generated[len(prompt):].strip()

            # Clean up — take first sentence
            question = question.split("\n")[0].strip()
            question = question.split("[")[0].strip()  # Remove if another token starts

            # Ensure it ends with ?
            if question and "?" in question:
                question = question[:question.index("?") + 1]
            elif question and not question.endswith("?"):
                question = question.rstrip(".!,") + "?"

            if len(question) < 10:
                return None  # Too short, skip

            return question

        except Exception as e:
            print(f"   ⚠️ LLM generation failed: {e}")
            return None

    # ─── Expert-crafted question templates (fallback) ──────────────

    QUESTION_TEMPLATES = {
        # ── Design & Brand ──────────────────────────────────────
        "design_style": [
            "What vibe are you going for visually? Think modern, minimal, bold, retro — anything inspire you?",
            "If you showed someone this project, what feeling should they get at first glance?",
            "Are there any websites, apps, or brands whose look you love? That helps me nail the direction.",
            "Do you lean more towards clean and simple, or rich and detailed?",
        ],
        "existing_branding": [
            "Do you already have brand assets — logo, color palette, fonts — or are we building from scratch?",
            "Is there an existing brand identity we should work within, or is this a fresh start?",
        ],
        "design_direction": [
            "Walk me through the mood — what colors, textures, or vibes are you imagining?",
            "If this project were a brand, how would you describe its personality in 3 words?",
        ],
        "color_preferences": [
            "Any colors that feel right for this? Or colors you absolutely want to avoid?",
        ],
        "visual_assets_needed": [
            "What visuals do we need to create? Photos, illustrations, icons, AI-generated images?",
        ],
        "visual_assets": [
            "What kind of visual content do you need — photos, graphics, video clips, animations?",
        ],

        # ── Audience ────────────────────────────────────────────
        "target_audience": [
            "Who's this really for? Paint me a picture of your ideal user or customer.",
            "Who are you trying to reach, and what do they care about most?",
            "Tell me about your audience — age, interests, what keeps them up at night.",
        ],
        "target_customers": [
            "Who's buying from you? What does a typical customer look like?",
        ],
        "target_market": [
            "What market are you going after? Local, national, global? Niche or broad?",
        ],
        "target_users": [
            "Who's going to actually use this day-to-day? What's their role?",
        ],
        "existing_audience_size": [
            "How big is your current reach — email list, social followers, customer base?",
        ],

        # ── Content & Messaging ─────────────────────────────────
        "key_message": [
            "If someone remembers just one thing about this project, what should it be?",
            "What's the core message? Boil it down to one sentence.",
        ],
        "messaging_tone": [
            "How should this sound — professional, casual, inspiring, playful, urgent?",
        ],
        "content_ready": [
            "How's the content looking — do you have text and images ready, or do we need to create everything?",
        ],
        "brand_voice": [
            "What tone should the writing have — formal, casual, witty, inspirational?",
        ],
        "brand_tone": [
            "What personality should come through in the messaging?",
        ],

        # ── Technical ───────────────────────────────────────────
        "tech_platform": [
            "Any preference on the tech side — WordPress, Shopify, custom code, something else?",
        ],
        "tech_stack": [
            "What tech are you using or planning to use? Frontend, backend, database?",
        ],

        # ── Scope & Deliverables ────────────────────────────────
        "deliverables": [
            "Let's get specific — what exactly do you need delivered at the end of this?",
        ],
        "pages_structure": [
            "What pages do you need? Home, About, Services, Contact — or something more custom?",
        ],
        "core_features": [
            "What are the must-have features — the things that make or break this project?",
        ],
        "campaign_channels": [
            "Where should this reach people — email, social media, paid ads, your website?",
        ],

        # ── Timeline & Budget ───────────────────────────────────
        "timeline": [
            "What's the timeline looking like? Any hard deadlines I should know about?",
        ],
        "budget": [
            "What budget range are you working with? Even a rough idea helps me scope things right.",
        ],

        # ── Campaign / Mission ──────────────────────────────────
        "campaign_goal": [
            "What's the #1 goal here — more sales, brand awareness, customer engagement?",
        ],
        "event_theme": [
            "What's the occasion or theme? Tell me the story behind this campaign.",
        ],
        "main_content_purpose": [
            "What's the main purpose of this — what problem does it solve or goal does it achieve?",
        ],
        "app_purpose": [
            "What problem does this app solve? What's the core use case?",
        ],
        "problem_solution": [
            "What specific problem does this SaaS solve, and who has that problem?",
        ],
        "offer_promotion": [
            "Is there a special offer or promotion tied to this — discount, free trial?",
        ],
        "products_services": [
            "What are you selling? Walk me through your product or service lineup.",
        ],

        # ── Email ───────────────────────────────────────────────
        "email_goals": [
            "What should email marketing achieve for you — sales, engagement, retention?",
        ],
        "email_types": [
            "What types of emails — newsletters, automated sequences, promotions, transactional?",
        ],
        "email_platform": [
            "Using an email platform already — Mailchimp, Klaviyo — or need a recommendation?",
        ],

        # ── Chatbot ─────────────────────────────────────────────
        "bot_purpose": [
            "What should the chatbot do — answer FAQs, handle orders, provide support?",
        ],

        # ── Video ───────────────────────────────────────────────
        "video_purpose": [
            "What's the goal of this video — promote, explain, educate, or inspire?",
        ],

        # ── UX ──────────────────────────────────────────────────
        "current_problems": [
            "What's broken right now? What are users complaining about or struggling with?",
        ],

        # ── Data ────────────────────────────────────────────────
        "data_sources": [
            "Where does the data come from? What systems, APIs, or databases feed into this?",
        ],
        "key_metrics": [
            "What metrics matter most? Revenue, engagement, conversion, retention?",
        ],
    }

    # ─── Multi-element cluster questions ───────────────────────────
    CLUSTER_TEMPLATES = {
        "design_and_brand": [
            "Let's talk about the look and feel — what visual style are you going for, and do you have existing brand assets (logo, colors, fonts) we should use?",
            "How should this look? Any design references you love, existing branding to work with, or color preferences?",
        ],
        "audience_and_reach": [
            "Tell me about who you're trying to reach — describe your ideal customer, and how big is your current audience?",
            "Let's define the audience — who are they, what do they care about, and how many of them can you reach today?",
        ],
        "content_and_messaging": [
            "What's the core message, and do you already have content ready — or do we need to create everything?",
            "Let's nail the messaging — what's the one thing people should take away, and what voice should we use?",
        ],
        "scope_and_deliverables": [
            "Let's define what you actually need delivered — what are all the concrete pieces that need to get done?",
        ],
        "business_and_logistics": [
            "Let's talk logistics — what's the timeline, and do you have a budget range in mind?",
            "When do you need this done, and what budget are we working with?",
        ],
        "offer_and_commerce": [
            "Is there a promotion or special offer tied to this? And what products or services are involved?",
        ],
        "technical_setup": [
            "What's the technical situation — what platform are you on, and are there tools or integrations we need to account for?",
        ],
    }

    def generate_candidates(self, elements: list[dict],
                            clusters: list[dict],
                            conversation_history: list[dict] = None,
                            n_candidates: int = 6,
                            mission_task: str = "") -> list[dict]:
        """
        Generate N candidate questions targeting different elements/clusters.

        Uses the fine-tuned LLM as primary generator, with template fallback.

        Returns list of candidates, each with:
        {
            "question": str,
            "targets": [element_names],
            "cluster": str,
            "score": float (reward score),
            "source": "llm" | "template"
        }
        """
        candidates = []
        conversation_history = conversation_history or []
        asked_topics = self._get_asked_topics(conversation_history)

        # Gather known/unknown elements for LLM context
        known_elements = [e for e in elements if e["status"] == "answered"]
        unknown_elements = [e for e in elements if e["status"] == "undefined"]
        unknown_elements.sort(key=lambda e: e["score"], reverse=True)

        # ───── Strategy 1: LLM-generated questions ─────────────
        if self._llm_model is not None and unknown_elements:
            # Generate 2-3 LLM questions with slightly different contexts
            for i in range(3):
                # Vary the unknown list slightly to get diverse questions
                shuffled_unknown = unknown_elements.copy()
                if i > 0:
                    # After first, shuffle to get variety
                    top = shuffled_unknown[:2]
                    rest = shuffled_unknown[2:]
                    random.shuffle(rest)
                    shuffled_unknown = top + rest

                llm_question = self._generate_llm_question(
                    mission_task=mission_task or "Project",
                    known_elements=known_elements,
                    unknown_elements=shuffled_unknown,
                    conversation_history=conversation_history,
                )

                if llm_question:
                    # Determine which elements this question targets
                    targets = self._match_question_to_elements(
                        llm_question, unknown_elements
                    )
                    if targets:
                        score = self._score_candidate(
                            targets=targets,
                            is_cluster=len(targets) > 1,
                            conversation_history=conversation_history,
                        )
                        candidates.append({
                            "question": llm_question,
                            "targets": [e["name"] for e in targets],
                            "cluster": None,
                            "score": score + 15,  # LLM bonus — prefer over templates
                            "source": "llm",
                        })

        # ───── Strategy 2: Cluster-level template questions ────
        for cluster in clusters:
            if cluster["all_answered"]:
                continue
            if cluster["cluster_name"] in asked_topics:
                continue

            templates = self.CLUSTER_TEMPLATES.get(cluster["cluster_name"], [])
            if templates:
                undefined = [e for e in cluster["elements"] if e["status"] == "undefined"]
                question = random.choice(templates)
                score = self._score_candidate(
                    targets=undefined,
                    is_cluster=True,
                    conversation_history=conversation_history,
                )
                candidates.append({
                    "question": question,
                    "targets": [e["name"] for e in undefined],
                    "cluster": cluster["cluster_name"],
                    "score": score,
                    "source": "template",
                })

        # ───── Strategy 3: Single element template questions ───
        for elem in unknown_elements[:5]:
            if elem["name"] in asked_topics:
                continue
            templates = self.QUESTION_TEMPLATES.get(elem["name"], [])
            if not templates and self._trained_templates:
                for cat_templates in self._trained_templates.values():
                    if elem["name"] in cat_templates:
                        templates = cat_templates[elem["name"]]
                        break
            if not templates:
                desc = elem.get("description", elem["name"].replace("_", " "))
                templates = [
                    f"Tell me about {desc.lower()} — what are you thinking?",
                ]
            if templates:
                question = random.choice(templates)
                score = self._score_candidate(
                    targets=[elem],
                    is_cluster=False,
                    conversation_history=conversation_history,
                )
                candidates.append({
                    "question": question,
                    "targets": [elem["name"]],
                    "cluster": None,
                    "score": score,
                    "source": "template",
                })

        # Deduplicate and sort by score
        seen_targets = set()
        unique_candidates = []
        for c in sorted(candidates, key=lambda x: x["score"], reverse=True):
            target_key = frozenset(c["targets"])
            if target_key not in seen_targets:
                seen_targets.add(target_key)
                unique_candidates.append(c)

        return unique_candidates[:n_candidates]

    def _match_question_to_elements(self, question: str,
                                     elements: list[dict]) -> list[dict]:
        """Match an LLM-generated question to the elements it likely targets."""
        question_lower = question.lower()
        matched = []

        for elem in elements:
            name_words = elem["name"].replace("_", " ").lower()
            desc_words = elem.get("description", "").lower().split()

            # Check if the question mentions this element
            name_match = any(
                word in question_lower
                for word in name_words.split()
                if len(word) > 3
            )
            desc_match = sum(
                1 for word in desc_words
                if len(word) > 3 and word in question_lower
            )

            if name_match or desc_match >= 2:
                matched.append(elem)

        # If no match found, assume it targets the highest-priority unknown
        if not matched and elements:
            matched = [elements[0]]

        return matched[:3]  # Cap at 3

    def select_best(self, candidates: list[dict]) -> Optional[dict]:
        """Select the highest-scoring candidate."""
        if not candidates:
            return None
        return max(candidates, key=lambda c: c["score"])

    def _score_candidate(self, targets: list[dict],
                         is_cluster: bool,
                         conversation_history: list[dict]) -> float:
        """
        PPO-style reward function using trained weights.

        Reward = coverage_gain + multi_element_bonus + timing_bonus
        """
        coverage_gain = sum(t["score"] for t in targets)

        w = self._reward_weights or {}
        multi_bonus_weight = w.get("multi_element_bonus", 15)
        cluster_bonus_weight = w.get("cluster_bonus", 25)

        multi_bonus = len(targets) * multi_bonus_weight if len(targets) > 1 else 0
        cluster_bonus = cluster_bonus_weight if is_cluster else 0

        turn_number = len(conversation_history)
        avg_target_score = coverage_gain / max(len(targets), 1)
        timing_bonus = 10 if (turn_number < 3 and avg_target_score > 70) else 0

        return coverage_gain + multi_bonus + cluster_bonus + timing_bonus

    def _get_asked_topics(self, conversation_history: list[dict]) -> set:
        """Extract topics already asked about from conversation history."""
        asked = set()
        for turn in conversation_history:
            if "targets" in turn:
                asked.update(turn["targets"])
        return asked

    @property
    def has_llm(self) -> bool:
        """Check if the LLM is loaded and ready."""
        return self._llm_model is not None
