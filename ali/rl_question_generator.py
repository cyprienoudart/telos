"""
RL Question Generator (Component 3) — Generates candidate questions and selects the best.
Uses PPO reward logic to score candidates by expected coverage gain.

Loads trained templates and reward weights when available,
falls back to handcrafted templates otherwise.
"""
from __future__ import annotations

import json
import os
import random
from typing import Optional


class RLQuestionGenerator:
    """
    Component 3: Generate N candidate questions, score them, pick the best.

    The reward function favors questions that:
    - Target high-importance undefined elements
    - Cover multiple elements in one question (cluster questions)
    - Are specific and natural-sounding
    - Don't re-ask already-answered elements
    """

    def __init__(self, model_dir: str = "ali/trained_models"):
        """Load trained templates and weights if available."""
        self._trained_templates = None
        self._reward_weights = None

        # Try loading trained question templates
        templates_path = os.path.join(model_dir, "question_templates.json")
        if os.path.exists(templates_path):
            with open(templates_path, "r") as f:
                self._trained_templates = json.load(f)

        # Try loading trained reward weights
        weights_path = os.path.join(model_dir, "reward_weights.json")
        if os.path.exists(weights_path):
            with open(weights_path, "r") as f:
                self._reward_weights = json.load(f)

    # ─── Expert-crafted question templates ─────────────────────────
    # These are the hardcoded fallback — written like a real consultant.

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
            "Do you have a style guide or brand book, or should we define the visual identity as part of this?",
        ],
        "design_direction": [
            "Walk me through the mood — what colors, textures, or vibes are you imagining?",
            "If this project were a brand, how would you describe its personality in 3 words?",
            "Any visual references you love? Even outside your industry — restaurants, fashion brands, anything.",
        ],
        "color_preferences": [
            "Any colors that feel right for this? Or colors you absolutely want to avoid?",
            "What palette would feel on-brand — warm earth tones, cool blues, bold neons, elegant neutrals?",
        ],
        "visual_assets_needed": [
            "What visuals do we need to create? Photos, illustrations, icons, AI-generated images?",
            "Will we be using stock photography, custom shoots, or should I plan for AI-generated visuals?",
            "How image-heavy is this going to be? Just a few hero shots, or lots of visual content?",
        ],
        "visual_assets": [
            "What kind of visual content do you need — photos, graphics, video clips, animations?",
            "Do you have existing imagery we can work with, or does everything need to be created?",
        ],

        # ── Audience ────────────────────────────────────────────
        "target_audience": [
            "Who's this really for? Paint me a picture of your ideal user or customer.",
            "If you described your perfect customer to a friend, what would you say?",
            "Who are you trying to reach, and what do they care about most?",
            "Tell me about your audience — age, interests, what keeps them up at night.",
        ],
        "target_customers": [
            "Who's buying from you? What does a typical customer look like?",
            "Describe your dream customer — who are they and why would they choose you?",
        ],
        "target_market": [
            "What market are you going after? Local, national, global? Niche or broad?",
            "Who's your ideal buyer and where do they hang out — online and offline?",
        ],
        "target_users": [
            "Who's going to actually use this day-to-day? What's their role?",
            "Walk me through a typical user — what are they trying to accomplish?",
        ],
        "existing_audience_size": [
            "How big is your current reach — email list, social followers, customer base?",
            "Give me a sense of scale — how many people can you reach today through your existing channels?",
        ],
        "audience_size": [
            "How many people are we trying to reach? What's your current audience size?",
            "What's the scale we're working with — hundreds, thousands, tens of thousands?",
        ],

        # ── Content & Messaging ─────────────────────────────────
        "key_message": [
            "If someone remembers just one thing about this project, what should it be?",
            "What's the core message? Boil it down to one sentence.",
            "What do you want people to feel or understand after interacting with this?",
        ],
        "messaging_tone": [
            "How should this sound — professional, casual, inspiring, playful, urgent?",
            "If this project could talk, what's its personality? Corporate and polished, or friendly and approachable?",
        ],
        "content_ready": [
            "How's the content looking — do you have text and images ready, or do we need to create everything?",
            "Is the copywriting done, or is that something we need to build as part of this project?",
        ],
        "brand_voice": [
            "What tone should the writing have — formal, casual, witty, inspirational?",
            "How do you talk to your audience? Like a friend, a mentor, or a trusted advisor?",
        ],
        "brand_tone": [
            "What personality should come through in the messaging — warm, bold, serious, fun?",
            "Describe the voice — if your brand were a person, how would they talk?",
        ],

        # ── Technical ───────────────────────────────────────────
        "tech_platform": [
            "Any preference on the tech side — WordPress, Shopify, custom code, something else?",
            "What's the technical setup? Are you on an existing platform or starting fresh?",
            "Do you have a preference for the tech stack, or should I recommend based on your needs?",
        ],
        "existing_platform": [
            "What are you currently running on? What platform or tools do you use today?",
            "Tell me about your current setup — what's working, what's not?",
        ],
        "platform_preference": [
            "Do you have a platform in mind — Shopify, WooCommerce, custom — or are you open to suggestions?",
        ],
        "tech_stack": [
            "What tech are you using or planning to use? Frontend, backend, database?",
            "Any tech requirements or constraints I should know about?",
        ],

        # ── Scope & Deliverables ────────────────────────────────
        "deliverables": [
            "Let's get specific — what exactly do you need delivered at the end of this?",
            "What are the concrete outputs? Website pages, email templates, graphics, documents?",
            "If you made a checklist of everything you need, what would be on it?",
        ],
        "pages_structure": [
            "What pages do you need? Home, About, Services, Contact — or something more custom?",
            "Walk me through the site structure — what sections or pages are must-haves?",
        ],
        "core_features": [
            "What are the must-have features — the things that make or break this project?",
            "If you could only have 3 features, which ones are non-negotiable?",
            "What functionality is essential for this to work for your users?",
        ],
        "campaign_channels": [
            "Where should this reach people — email, social media, paid ads, your website, all of the above?",
            "Which channels matter most for your audience? Where do they spend their time?",
        ],
        "promotion_channel": [
            "How are you planning to get the word out — email blasts, social posts, paid ads, in-store?",
        ],

        # ── Timeline & Budget ───────────────────────────────────
        "timeline": [
            "What's the timeline looking like? Any hard deadlines I should know about?",
            "When do you need this done? Is there flexibility, or is the date locked in?",
            "How urgent is this — are we talking days, weeks, or months?",
        ],
        "campaign_dates": [
            "When does this need to go live? Any key dates we need to hit?",
            "Are there specific dates tied to this — a launch, event, or seasonal window?",
        ],
        "campaign_duration": [
            "How long should this campaign run — a one-time push or an ongoing sequence?",
        ],
        "budget": [
            "What budget range are you working with? Even a rough idea helps me scope things right.",
            "Any budget constraints? I want to make sure my recommendations are realistic.",
        ],
        "budget_range": [
            "Do you have a budget in mind for this project?",
            "What's the investment range you're comfortable with?",
        ],

        # ── Offer & Commerce ────────────────────────────────────
        "offer_promotion": [
            "Is there a special offer or promotion tied to this — discount, free trial, limited-time deal?",
            "Any incentive to drive action? Discounts, bundles, early access?",
        ],
        "offer_incentive": [
            "What's the hook to get people to act — a discount code, free shipping, a gift?",
            "Are you running a promotion with this, or is it more of an awareness play?",
        ],
        "products_services": [
            "What are you selling? Walk me through your product or service lineup.",
            "Tell me about what you offer — products, services, packages?",
        ],
        "pricing_strategy": [
            "How are you pricing things? Fixed prices, tiers, subscriptions?",
        ],

        # ── Mission-level ───────────────────────────────────────
        "campaign_goal": [
            "What's the #1 goal here — more sales, brand awareness, customer engagement?",
            "If this campaign is wildly successful, what does that look like?",
        ],
        "campaign_objectives": [
            "What are you trying to achieve — more revenue, more signups, more awareness?",
            "What does success look like for you? How will you know this worked?",
        ],
        "event_theme": [
            "What's the occasion or theme? Tell me the story behind this campaign.",
            "What event or moment are we building around?",
        ],
        "main_content_purpose": [
            "What's the main purpose of this — what problem does it solve or goal does it achieve?",
            "Why does this need to exist? What happens if you don't do it?",
        ],
        "app_purpose": [
            "What problem does this app solve? What's the core use case?",
            "In one sentence, why would someone download this app?",
        ],
        "data_sources": [
            "Where does the data come from? What systems, APIs, or databases feed into this?",
        ],
        "key_metrics": [
            "What metrics matter most? Revenue, engagement, conversion, retention?",
        ],

        # ── Email marketing ─────────────────────────────────────
        "email_goals": [
            "What should email marketing achieve for you — sales, engagement, retention, nurturing?",
        ],
        "target_subscribers": [
            "Who should be on your email list? How are you planning to grow it?",
        ],
        "email_types": [
            "What types of emails do you need — newsletters, automated sequences, promotions, transactional?",
        ],
        "sending_frequency": [
            "How often do you want to email your list — daily, weekly, monthly?",
        ],
        "email_platform": [
            "Are you using an email platform already — Mailchimp, Klaviyo, ConvertKit — or do we need to pick one?",
        ],
        "content_strategy": [
            "What kind of content goes in the emails? Educational, promotional, mixed?",
        ],
        "design_template": [
            "Do you need email templates designed, or do you have existing ones to work with?",
        ],
        "segmentation": [
            "How should we segment your audience — by behavior, interests, purchase history?",
        ],
        "automation_flows": [
            "What automated sequences do you need — welcome series, abandoned cart, re-engagement?",
        ],

        # ── SaaS specifics ──────────────────────────────────────
        "problem_solution": [
            "What specific problem does this SaaS solve, and who has that problem?",
        ],
        "pricing_model": [
            "How will you charge — free trial, freemium, flat subscription, usage-based?",
        ],
        "user_auth_roles": [
            "What kind of user management do you need — simple login, team accounts, admin roles?",
        ],
        "data_model": [
            "What are the core data entities? Users, projects, tasks, transactions?",
        ],
        "onboarding_flow": [
            "How should new users get started — guided wizard, free exploration, video tutorials?",
        ],

        # ── Chatbot specifics ───────────────────────────────────
        "bot_purpose": [
            "What should the chatbot do — answer FAQs, handle orders, provide support?",
        ],
        "use_cases": [
            "Walk me through 3 typical conversations this bot should handle.",
        ],
        "knowledge_base": [
            "What information does the bot need access to — product catalog, FAQs, policies?",
        ],
        "tone_personality": [
            "What should the bot's personality be — professional, friendly, witty?",
        ],
        "platform_deployment": [
            "Where should the bot live — your website, WhatsApp, Slack, Discord?",
        ],
        "ai_model": [
            "Do you have a preference for the AI backbone — GPT, Claude, open-source?",
        ],

        # ── Video specifics ─────────────────────────────────────
        "video_purpose": [
            "What's the goal of this video — promote, explain, educate, or inspire?",
        ],
        "video_length": [
            "How long should the video be? 15-second social clip, 2-minute explainer, or longer?",
        ],
        "video_style": [
            "What style — live action, animation, motion graphics, screen recording, mix?",
        ],
        "script_content": [
            "Do you have a script or talking points, or do we need to write that too?",
        ],
        "distribution_platform": [
            "Where will this video be published — YouTube, TikTok, your website, ads?",
        ],

        # ── UX redesign specifics ───────────────────────────────
        "current_problems": [
            "What's broken right now? What are users complaining about or struggling with?",
        ],
        "scope": [
            "Is this a full redesign or are we focusing on specific pages or user flows?",
        ],
        "user_research": [
            "Do you have any user research, analytics data, or feedback we can start from?",
        ],
        "key_user_flows": [
            "What are the critical user journeys — signup, checkout, search, onboarding?",
        ],
        "success_metrics": [
            "How will we measure if the UX improvements actually work? Conversion rate, support tickets, task completion?",
        ],
    }

    # ─── Multi-element cluster questions ───────────────────────────
    CLUSTER_TEMPLATES = {
        "design_and_brand": [
            "Let's talk about the look and feel — what visual style are you going for, and do you have existing brand assets (logo, colors, fonts) we should use?",
            "Walk me through the visual direction — mood, colors, and whether you have brand guidelines already or we're creating them.",
            "How should this look? Any design references you love, existing branding to work with, or color preferences?",
        ],
        "audience_and_reach": [
            "Tell me about who you're trying to reach — describe your ideal customer, and how big is your current audience?",
            "Who is this for? Paint me a picture of your target audience, and give me a sense of your current reach.",
            "Let's define the audience — who are they, what do they care about, and how many of them can you reach today?",
        ],
        "content_and_messaging": [
            "What's the core message, and do you already have content ready — or do we need to create everything?",
            "What should this say and how should it sound? Give me the key message and the tone you want.",
            "Let's nail the messaging — what's the one thing people should take away, and what voice should we use?",
        ],
        "scope_and_deliverables": [
            "Let's define what you actually need delivered — what are all the concrete pieces that need to get done?",
            "What's the full scope? Walk me through every deliverable you're expecting.",
            "If you wrote a shopping list of everything this project needs to produce, what's on it?",
        ],
        "business_and_logistics": [
            "Let's talk logistics — what's the timeline, and do you have a budget range in mind?",
            "When do you need this done, and what budget are we working with? Even rough numbers help.",
            "What's the timeline pressure and budget reality? I want to set realistic expectations.",
        ],
        "offer_and_commerce": [
            "Is there a promotion or special offer tied to this? And what products or services are involved?",
            "What's the commercial angle — any discounts, deals, or incentives to drive action?",
        ],
        "technical_setup": [
            "What's the technical situation — what platform are you on, and are there tools or integrations we need to account for?",
            "Let's talk tech — any platform preferences, existing systems, or tools that need to work together?",
        ],
    }

    def generate_candidates(self, elements: list[dict],
                            clusters: list[dict],
                            conversation_history: list[dict] = None,
                            n_candidates: int = 6) -> list[dict]:
        """
        Generate N candidate questions targeting different elements/clusters.

        Returns list of candidates, each with:
        {
            "question": str,
            "targets": [element_names],
            "cluster": str,
            "score": float (reward score)
        }
        """
        candidates = []
        conversation_history = conversation_history or []
        asked_topics = self._get_asked_topics(conversation_history)

        # Strategy 1: Cluster-level questions (highest value)
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
                })

        # Strategy 2: Single high-importance element questions
        undefined_elements = [e for e in elements if e["status"] == "undefined"]
        undefined_elements.sort(key=lambda e: e["score"], reverse=True)

        for elem in undefined_elements[:5]:
            if elem["name"] in asked_topics:
                continue
            templates = self.QUESTION_TEMPLATES.get(elem["name"], [])
            # Fallback: use trained templates
            if not templates and self._trained_templates:
                for cat_templates in self._trained_templates.values():
                    if elem["name"] in cat_templates:
                        templates = cat_templates[elem["name"]]
                        break
            if not templates:
                # Generate from element description
                desc = elem.get("description", elem["name"].replace("_", " "))
                templates = [
                    f"Tell me about {desc.lower()} — what are you thinking?",
                    f"What's the plan for {desc.lower()}?",
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

    def select_best(self, candidates: list[dict]) -> Optional[dict]:
        """Select the highest-scoring candidate."""
        if not candidates:
            return None
        return max(candidates, key=lambda c: c["score"])

    def _score_candidate(self, targets: list[dict],
                         is_cluster: bool,
                         conversation_history: list[dict]) -> float:
        """
        PPO-style reward function (heuristic version for hackathon).

        Reward = coverage_gain + multi_element_bonus + timing_bonus - redundancy_penalty
        """
        # Coverage gain: sum of target element scores
        coverage_gain = sum(t["score"] for t in targets)

        # Load trained weights or use defaults
        w = self._reward_weights or {}
        multi_bonus_weight = w.get("multi_element_bonus", 15)
        cluster_bonus_weight = w.get("cluster_bonus", 25)

        # Multi-element bonus: reward covering 2+ elements in one question
        multi_bonus = len(targets) * multi_bonus_weight if len(targets) > 1 else 0

        # Cluster bonus: prefer cluster questions
        cluster_bonus = cluster_bonus_weight if is_cluster else 0

        # Early conversation bonus: ask high-importance questions first
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
