#!/usr/bin/env python3
"""
Generate SFT training data for the question-generation LLM.

Creates prompt → question pairs in the format:
  Input:  [MISSION] ... [KNOWN] ... [UNKNOWN] ... [HISTORY] ...
  Output: [QUESTION] ...

These are used to fine-tune GPT-2 to generate context-aware questions.
"""
from __future__ import annotations

import json
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

OUTPUT_PATH = "training_data/question_sft_data.jsonl"
MISSIONS_PATH = "training_data/missions.jsonl"

# Hand-crafted expert questions indexed by element name.
# These become the ground-truth answers during fine-tuning.
EXPERT_QUESTIONS = {
    "main_content_purpose": [
        "What's the main purpose of this project — what problem does it solve?",
        "Why does this need to exist? What happens if you don't do it?",
    ],
    "target_audience": [
        "Who's this really for? Paint me a picture of your ideal user or customer.",
        "Who are you trying to reach, and what do they care about most?",
        "Tell me about your audience — age, interests, what keeps them up at night.",
    ],
    "target_users": [
        "Who's going to actually use this day-to-day? What's their role?",
        "Walk me through a typical user — what are they trying to accomplish?",
    ],
    "target_customers": [
        "Who's buying from you? What does a typical customer look like?",
        "Describe your dream customer — who are they and why would they choose you?",
    ],
    "target_market": [
        "What market are you going after? Local, national, global? Niche or broad?",
        "Who's your ideal buyer and where do they hang out?",
    ],
    "design_style": [
        "What vibe are you going for visually? Modern, minimal, bold, retro?",
        "Are there any websites or brands whose look you love?",
    ],
    "design_direction": [
        "Walk me through the mood — colors, textures, vibes?",
        "If this project were a brand, how would you describe its personality in 3 words?",
    ],
    "existing_branding": [
        "Do you already have brand assets — logo, colors, fonts — or starting from scratch?",
        "Is there an existing brand identity we should work within?",
    ],
    "color_preferences": [
        "Any colors that feel right for this? Or colors you want to avoid?",
        "What palette would feel on-brand — warm, cool, bold, neutral?",
    ],
    "core_features": [
        "What are the must-have features — the things that make or break this project?",
        "If you could only have 3 features, which ones are non-negotiable?",
    ],
    "pages_structure": [
        "What pages do you need? Home, About, Services, Contact — or more custom?",
        "Walk me through the site structure — what sections are must-haves?",
    ],
    "tech_platform": [
        "Any preference on the tech side — WordPress, Shopify, custom code?",
        "What's the technical setup? Existing platform or starting fresh?",
    ],
    "tech_stack": [
        "What tech are you using or planning to use?",
        "Any tech requirements or constraints I should know about?",
    ],
    "content_ready": [
        "How's the content looking — text and images ready, or need to create everything?",
        "Is the copywriting done, or part of this project?",
    ],
    "timeline": [
        "What's the timeline? Any hard deadlines?",
        "When do you need this done? Is there flexibility?",
    ],
    "budget": [
        "What budget range are you working with? Even rough helps.",
        "Any budget constraints I should know about?",
    ],
    "budget_range": [
        "Do you have a budget in mind for this project?",
    ],
    "key_message": [
        "If someone remembers one thing about this, what should it be?",
        "What's the core message? Boil it down to one sentence.",
    ],
    "messaging_tone": [
        "How should this sound — professional, casual, inspiring, playful?",
    ],
    "brand_voice": [
        "What tone should the writing have — formal, casual, witty?",
    ],
    "brand_tone": [
        "What personality should come through in the messaging?",
    ],
    "campaign_goal": [
        "What's the #1 goal — more sales, brand awareness, engagement?",
        "If this campaign is wildly successful, what does that look like?",
    ],
    "campaign_channels": [
        "Where should this reach people — email, social, ads, website?",
        "Which channels matter most for your audience?",
    ],
    "offer_promotion": [
        "Is there a special offer tied to this — discount, free trial?",
    ],
    "offer_incentive": [
        "What's the hook to get people to act — discount, free shipping?",
    ],
    "products_services": [
        "What are you selling? Walk me through your product lineup.",
    ],
    "deliverables": [
        "What exactly needs to be delivered at the end?",
        "If you made a checklist of everything needed, what's on it?",
    ],
    "campaign_dates": [
        "When does this need to go live? Any key dates?",
    ],
    "app_purpose": [
        "What problem does this app solve? Core use case?",
    ],
    "problem_solution": [
        "What specific problem does this SaaS solve, and who has that problem?",
    ],
    "data_sources": [
        "Where does the data come from? What systems feed into this?",
    ],
    "key_metrics": [
        "What metrics matter most? Revenue, engagement, conversion?",
    ],
    "email_goals": [
        "What should email marketing achieve — sales, engagement, retention?",
    ],
    "email_types": [
        "What types of emails — newsletters, automated sequences, promotions?",
    ],
    "email_platform": [
        "Using an email platform already — Mailchimp, Klaviyo — or need one?",
    ],
    "bot_purpose": [
        "What should the chatbot do — FAQs, orders, support?",
    ],
    "video_purpose": [
        "What's the goal of this video — promote, explain, educate?",
    ],
    "current_problems": [
        "What's broken right now? What are users struggling with?",
    ],
    "event_theme": [
        "What's the occasion or theme? Tell me the story behind this.",
    ],
    "pricing_strategy": [
        "How are you pricing — fixed, tiers, subscriptions?",
    ],
    "pricing_model": [
        "How will you charge — free trial, freemium, subscription?",
    ],
    "visual_assets": [
        "What kind of visual content — photos, graphics, videos?",
    ],
    "visual_assets_needed": [
        "What visuals do we need to create — hero images, product shots?",
    ],
    "existing_audience_size": [
        "How big is your current reach — email list, followers, customers?",
    ],
    "campaign_objectives": [
        "What are you trying to achieve — revenue, signups, awareness?",
    ],
    "success_metrics": [
        "How will we measure if this worked?",
    ],
    "scope": [
        "Is this a full redesign or specific pages and flows?",
    ],
    "content_type": [
        "What content — blog posts, videos, social media, podcasts?",
    ],
    "automation_flows": [
        "What automated sequences — welcome series, abandoned cart?",
    ],
    "segmentation": [
        "How should we segment your audience — behavior, interests?",
    ],
    "sending_frequency": [
        "How often do you want to email — daily, weekly, monthly?",
    ],
}


def build_prompt(mission_task: str, known_elements: list[dict],
                 unknown_elements: list[dict], history: list[str] = None) -> str:
    """Build the input prompt for the question-generation model."""
    lines = []
    lines.append(f"[MISSION] {mission_task}")

    if known_elements:
        known_str = ", ".join(e["name"].replace("_", " ") for e in known_elements[:5])
        lines.append(f"[KNOWN] {known_str}")
    else:
        lines.append("[KNOWN] nothing yet")

    if unknown_elements:
        unknown_str = ", ".join(
            f"{e['name'].replace('_', ' ')} ({e['score']})"
            for e in unknown_elements[:8]
        )
        lines.append(f"[UNKNOWN] {unknown_str}")

    if history:
        for i, q in enumerate(history[-3:], 1):
            lines.append(f"[Q{i}] {q}")

    lines.append("[QUESTION]")
    return " ".join(lines)


def generate_training_data():
    """Generate training data for the question-generation LLM."""
    missions = []
    with open(MISSIONS_PATH, "r") as f:
        for line in f:
            line = line.strip()
            if line:
                missions.append(json.loads(line))

    pairs = []

    for mission in missions:
        elements = mission["elements"]

        # Generate many scenarios varying what's known vs unknown
        for _ in range(50):
            # Random number of pre-answered elements
            num_known = random.randint(0, len(elements) - 2)
            indices = list(range(len(elements)))
            random.shuffle(indices)
            known_idx = set(indices[:num_known])

            known_elements = [elements[i] for i in range(len(elements)) if i in known_idx]
            unknown_elements = [elements[i] for i in range(len(elements)) if i not in known_idx]
            unknown_elements.sort(key=lambda e: e["score"], reverse=True)

            # The target question should address the highest-priority unknowns
            top_unknown = unknown_elements[0] if unknown_elements else None
            if not top_unknown:
                continue

            # Get an expert question for this element, or generate one
            questions = EXPERT_QUESTIONS.get(top_unknown["name"], [])
            if not questions:
                desc = top_unknown["description"]
                questions = [
                    f"Tell me about {desc.lower()} — what are you thinking?",
                    f"What's your plan for {desc.lower()}?",
                ]

            question = random.choice(questions)

            # Sometimes also add a cluster-style multi-element question
            if len(unknown_elements) >= 2 and random.random() < 0.3:
                second = unknown_elements[1]
                desc1 = top_unknown["description"].lower()
                desc2 = second["description"].lower()
                question = f"Let's cover two things — {desc1}, and {desc2}. What are your thoughts on both?"

            # Build simulated history for some examples
            history = None
            if num_known > 0 and random.random() < 0.5:
                # Simulate some prior Q&A
                prev_questions = []
                for ki in random.sample(list(known_idx), min(2, len(known_idx))):
                    prev_elem = elements[ki]
                    prev_qs = EXPERT_QUESTIONS.get(prev_elem["name"], [])
                    if prev_qs:
                        prev_questions.append(random.choice(prev_qs))
                if prev_questions:
                    history = prev_questions

            prompt = build_prompt(mission["task"], known_elements,
                                  unknown_elements, history)

            pairs.append({
                "text": f"{prompt} {question}",
                "prompt": prompt,
                "question": question,
                "target_element": top_unknown["name"],
                "category": mission["category"],
            })

    # Shuffle
    random.shuffle(pairs)

    # Write
    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    with open(OUTPUT_PATH, "w") as f:
        for pair in pairs:
            f.write(json.dumps(pair) + "\n")

    print(f"✅ Generated {len(pairs)} question SFT training examples")
    print(f"📄 Saved to: {OUTPUT_PATH}")
    print(f"📊 Categories: {len(missions)}")

    # Show examples
    print("\n📝 Sample training examples:")
    for pair in pairs[:3]:
        print(f"\n  PROMPT: {pair['prompt'][:120]}...")
        print(f"  QUESTION: {pair['question']}")

    return pairs


if __name__ == "__main__":
    generate_training_data()
