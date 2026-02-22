#!/usr/bin/env python3
"""
Generate SFT training data for the C1 (Mission Identifier) LLM.

Creates prompt → identification pairs in the format:
  Input:  [MISSION] user text describing their project
  Output: [IDENTIFY] category: <category> | elements: name=score, name=score, ...

Uses existing sft_pairs.jsonl (475 examples) as the base and augments
with rephrased / multi-category variants to reach ~800-1000 examples.

Output: train/data/c1_sft_data.jsonl
"""
from __future__ import annotations

import json
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

OUTPUT_PATH = "train/data/c1_sft_data.jsonl"
SFT_PAIRS_PATH = "train/data/sft_pairs.jsonl"
MISSIONS_PATH = "train/data/missions.jsonl"

# ── Augmentation templates for rephrasing ──
REPHRASE_PREFIXES = [
    "I need help with",
    "We want to",
    "Can you help me",
    "Looking for someone to",
    "I'd like to",
    "We're looking to",
    "Help me",
    "I want to build",
    "Our company needs",
    "Please create",
    "Build me",
    "I'm looking for",
    "We need",
    "Set up",
    "I require",
    "Our team wants to create",
    "We're planning to launch",
    "Could you design",
    "I'm interested in creating",
    "We'd love to have",
]

# ── Domain contexts for augmentation ──
BUSINESS_TYPES = [
    "bakery", "law firm", "dental clinic", "yoga studio", "fitness center",
    "restaurant", "consulting firm", "photography studio", "tech startup",
    "nonprofit organization", "real estate agency", "fashion boutique",
    "coffee shop", "auto repair shop", "pet store", "music school",
    "travel agency", "accounting firm", "marketing agency", "salon",
    "florist shop", "bookstore", "gym", "construction company",
    "medical practice", "architecture firm", "tutoring center", "brewery",
    "catering service", "event planning company", "daycare center",
    "insurance agency", "cleaning service", "landscaping business",
    "food truck", "wine bar", "coworking space", "art gallery",
]

# ── Multi-category combination patterns ──
MULTI_CATEGORY_TEMPLATES = [
    "I need a {type1} and also want to set up {type2}",
    "We want to {verb1} and at the same time {verb2}",
    "Our project involves {type1} combined with {type2}",
    "First, we need {type1}. We also want {type2}",
    "Looking for help with both {type1} and {type2}",
    "I need {type1} plus {type2} for my {business}",
    "We're planning {type1} alongside {type2}",
]

CATEGORY_PHRASES = {
    "web_development": [
        "a website", "a new website", "a web application", "a landing page",
        "to redesign our website", "a professional site",
    ],
    "marketing_campaign": [
        "a marketing campaign", "an ad campaign", "a promotional campaign",
        "a digital marketing push",
    ],
    "design_branding": [
        "brand identity", "a new logo and branding", "a visual identity",
        "brand guidelines", "a rebrand",
    ],
    "content_creation": [
        "content strategy", "blog content", "a content plan",
        "copywriting and articles",
    ],
    "ecommerce": [
        "an online store", "an e-commerce shop", "a Shopify store",
        "to sell products online",
    ],
    "mobile_app": [
        "a mobile app", "an iOS app", "an Android app",
        "a cross-platform mobile application",
    ],
    "data_analytics": [
        "a data dashboard", "analytics reporting", "a metrics dashboard",
        "business intelligence tools",
    ],
    "event_campaign": [
        "an event campaign", "a themed campaign", "a seasonal promotion",
        "a launch event",
    ],
    "saas_product": [
        "a SaaS product", "a subscription platform", "a cloud service",
        "a software product",
    ],
    "social_media": [
        "a social media strategy", "social media management",
        "to grow our social presence", "an Instagram strategy",
    ],
    "api_backend": [
        "an API", "a backend service", "a REST API",
        "a microservice architecture",
    ],
    "video_production": [
        "a promotional video", "video production", "an explainer video",
        "a brand video",
    ],
    "email_marketing": [
        "email marketing", "a newsletter system", "email automation",
        "a drip campaign",
    ],
    "chatbot_ai": [
        "a chatbot", "an AI assistant", "a customer service bot",
        "a conversational AI",
    ],
    "ux_redesign": [
        "a UX redesign", "UX improvements", "a usability audit",
        "UI/UX improvements",
    ],
}

CATEGORY_VERBS = {
    "web_development": "build a website",
    "marketing_campaign": "run a marketing campaign",
    "design_branding": "create brand identity",
    "content_creation": "develop a content strategy",
    "ecommerce": "launch an online store",
    "mobile_app": "build a mobile app",
    "data_analytics": "set up analytics dashboards",
    "event_campaign": "plan a themed campaign",
    "saas_product": "build a SaaS product",
    "social_media": "manage social media",
    "api_backend": "develop an API backend",
    "video_production": "produce video content",
    "email_marketing": "set up email marketing",
    "chatbot_ai": "build a chatbot",
    "ux_redesign": "redesign the user experience",
}


def build_identify_prompt(user_text: str) -> str:
    """Build the input prompt for the C1 model."""
    return f"[MISSION] {user_text} [IDENTIFY]"


def build_identify_output(category: str, elements: list[dict]) -> str:
    """Build the expected output for the C1 model.
    Format: category: <cat> | elements: name=score, name=score, ...
    """
    elem_parts = [f"{e['name']}={e['score']}" for e in elements]
    return f"category: {category} | elements: {', '.join(elem_parts)}"


def build_multi_identify_output(categories: list[str],
                                all_elements: list[dict]) -> str:
    """Build output for multi-category identification.
    Format: category: cat1, cat2 | elements: name=score, ...
    """
    cat_str = ", ".join(categories)
    elem_parts = [f"{e['name']}={e['score']}" for e in all_elements]
    return f"category: {cat_str} | elements: {', '.join(elem_parts)}"


def generate_training_data():
    """Generate training data for the C1 LLM."""

    # Load existing SFT pairs
    sft_pairs = []
    with open(SFT_PAIRS_PATH, "r") as f:
        for line in f:
            line = line.strip()
            if line:
                sft_pairs.append(json.loads(line))

    # Load missions (for element definitions)
    missions = []
    with open(MISSIONS_PATH, "r") as f:
        for line in f:
            line = line.strip()
            if line:
                missions.append(json.loads(line))

    mission_by_cat = {m["category"]: m for m in missions}
    all_categories = list(mission_by_cat.keys())

    pairs = []

    # ═════════════════════════════════════════════════════════════════
    # Strategy 1: Direct conversion from sft_pairs.jsonl
    # Each pair already has input, category, and output (elements)
    # ═════════════════════════════════════════════════════════════════
    seen_inputs = set()
    for sp in sft_pairs:
        user_input = sp["input"]
        category = sp["category"]
        elements = sp["output"]  # list of {name, score, description}

        # Deduplicate
        if user_input in seen_inputs:
            continue
        seen_inputs.add(user_input)

        prompt = build_identify_prompt(user_input)
        output = build_identify_output(category, elements)

        pairs.append({
            "text": f"{prompt} {output}",
            "prompt": prompt,
            "output": output,
            "category": category,
            "categories": sp.get("categories", [category]),
        })

    print(f"  Strategy 1 (direct from sft_pairs): {len(pairs)} examples")

    # ═════════════════════════════════════════════════════════════════
    # Strategy 2: Rephrased variants — take existing inputs and
    # generate new phrasings with different prefixes + business types
    # ═════════════════════════════════════════════════════════════════
    strategy2_count = 0
    for category, phrases in CATEGORY_PHRASES.items():
        if category not in mission_by_cat:
            continue
        elements = mission_by_cat[category]["elements"]

        for _ in range(20):
            prefix = random.choice(REPHRASE_PREFIXES)
            phrase = random.choice(phrases)
            business = random.choice(BUSINESS_TYPES)

            # Vary the construction
            r = random.random()
            if r < 0.3:
                user_text = f"{prefix} {phrase} for my {business}"
            elif r < 0.6:
                user_text = f"{prefix} {phrase}"
            elif r < 0.8:
                user_text = f"{prefix} {phrase} for our {business}. We need it done soon."
            else:
                user_text = f"{prefix} {phrase} targeting young professionals in the {business} industry"

            prompt = build_identify_prompt(user_text)
            output = build_identify_output(category, elements)

            pairs.append({
                "text": f"{prompt} {output}",
                "prompt": prompt,
                "output": output,
                "category": category,
                "categories": [category],
            })
            strategy2_count += 1

    print(f"  Strategy 2 (rephrased variants): {strategy2_count} examples")

    # ═════════════════════════════════════════════════════════════════
    # Strategy 3: Multi-category inputs — user describes 2 tasks
    # ═════════════════════════════════════════════════════════════════
    strategy3_count = 0
    for _ in range(100):
        # Pick 2 different categories
        cat1, cat2 = random.sample(all_categories, 2)
        if cat1 not in CATEGORY_PHRASES or cat2 not in CATEGORY_PHRASES:
            continue

        phrase1 = random.choice(CATEGORY_PHRASES[cat1])
        phrase2 = random.choice(CATEGORY_PHRASES[cat2])
        template = random.choice(MULTI_CATEGORY_TEMPLATES)

        if "{verb1}" in template:
            v1 = CATEGORY_VERBS.get(cat1, f"create {phrase1}")
            v2 = CATEGORY_VERBS.get(cat2, f"set up {phrase2}")
            user_text = template.format(verb1=v1, verb2=v2)
        elif "{business}" in template:
            business = random.choice(BUSINESS_TYPES)
            user_text = template.format(
                type1=phrase1, type2=phrase2, business=business
            )
        else:
            user_text = template.format(type1=phrase1, type2=phrase2)

        # Merge elements from both categories (dedup by name, keep highest score)
        merged = {}
        for cat in [cat1, cat2]:
            if cat in mission_by_cat:
                for e in mission_by_cat[cat]["elements"]:
                    if e["name"] not in merged or e["score"] > merged[e["name"]]["score"]:
                        merged[e["name"]] = e
        merged_elements = sorted(merged.values(), key=lambda x: x["score"], reverse=True)

        prompt = build_identify_prompt(user_text)
        output = build_multi_identify_output([cat1, cat2], merged_elements)

        pairs.append({
            "text": f"{prompt} {output}",
            "prompt": prompt,
            "output": output,
            "category": cat1,
            "categories": [cat1, cat2],
        })
        strategy3_count += 1

    print(f"  Strategy 3 (multi-category): {strategy3_count} examples")

    # ═════════════════════════════════════════════════════════════════
    # Strategy 4: Detailed mission descriptions with extra context
    # ═════════════════════════════════════════════════════════════════
    strategy4_count = 0
    detail_templates = [
        "{phrase} for my {biz}. Our target audience is {audience}. Budget is around {budget}.",
        "{phrase} for our {biz}. We want a {style} design with {color} colors.",
        "{phrase}. We're a {biz} looking to expand online. Timeline is {timeline}.",
        "We're a small {biz} and we need {phrase}. We already have a logo and brand guidelines.",
        "{phrase} for my {biz}. We want to reach {audience} and increase our online presence.",
        "I run a {biz} and need {phrase}. We have content ready and want to launch by {timeline}.",
    ]
    audiences = [
        "young professionals", "women 25-45", "local families", "small businesses",
        "students", "tech enthusiasts", "health-conscious consumers", "enterprise clients",
        "millennials", "Gen Z consumers", "parents", "seniors",
    ]
    budgets = [
        "1000 euros", "2000 euros", "3000-5000 euros", "5K",
        "10000 dollars", "under 2000", "flexible budget",
    ]
    styles = ["modern", "minimalist", "bold", "elegant", "playful", "professional", "clean"]
    colors = ["blue and white", "dark", "pastel", "bright", "warm", "neutral", "green and gold"]
    timelines = ["2 weeks", "next month", "Q2", "3 months", "end of March", "ASAP"]

    for category, phrases in CATEGORY_PHRASES.items():
        if category not in mission_by_cat:
            continue
        elements = mission_by_cat[category]["elements"]

        for _ in range(10):
            template = random.choice(detail_templates)
            phrase = random.choice(phrases)
            biz = random.choice(BUSINESS_TYPES)

            user_text = template.format(
                phrase=phrase,
                biz=biz,
                audience=random.choice(audiences),
                budget=random.choice(budgets),
                style=random.choice(styles),
                color=random.choice(colors),
                timeline=random.choice(timelines),
            )

            prompt = build_identify_prompt(user_text)
            output = build_identify_output(category, elements)

            pairs.append({
                "text": f"{prompt} {output}",
                "prompt": prompt,
                "output": output,
                "category": category,
                "categories": [category],
            })
            strategy4_count += 1

    print(f"  Strategy 4 (detailed missions): {strategy4_count} examples")

    # ═════════════════════════════════════════════════════════════════
    # Strategy 5: Short / terse inputs
    # ═════════════════════════════════════════════════════════════════
    strategy5_count = 0
    for category, phrases in CATEGORY_PHRASES.items():
        if category not in mission_by_cat:
            continue
        elements = mission_by_cat[category]["elements"]

        short_inputs = [
            random.choice(phrases),
            f"Need {random.choice(phrases)}",
            f"{random.choice(phrases)} please",
            f"Help with {random.choice(phrases)}",
            f"{random.choice(phrases)} for my business",
        ]

        for user_text in short_inputs:
            prompt = build_identify_prompt(user_text)
            output = build_identify_output(category, elements)

            pairs.append({
                "text": f"{prompt} {output}",
                "prompt": prompt,
                "output": output,
                "category": category,
                "categories": [category],
            })
            strategy5_count += 1

    print(f"  Strategy 5 (short inputs): {strategy5_count} examples")

    # ═════════════════════════════════════════════════════════════════
    # Shuffle and write
    # ═════════════════════════════════════════════════════════════════
    random.shuffle(pairs)

    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    with open(OUTPUT_PATH, "w") as f:
        for pair in pairs:
            f.write(json.dumps(pair) + "\n")

    print(f"\n✅ Generated {len(pairs)} C1 SFT training examples")
    print(f"📄 Saved to: {OUTPUT_PATH}")

    # Stats
    cat_counts = {}
    for p in pairs:
        for c in p["categories"]:
            cat_counts[c] = cat_counts.get(c, 0) + 1
    print(f"📊 Categories covered: {len(cat_counts)}")
    for cat, count in sorted(cat_counts.items(), key=lambda x: -x[1]):
        print(f"   {cat}: {count}")

    single = sum(1 for p in pairs if len(p["categories"]) == 1)
    multi = sum(1 for p in pairs if len(p["categories"]) > 1)
    print(f"\n   Single-category: {single}, Multi-category: {multi}")

    # Show examples
    print("\n📝 Sample training examples:")
    for pair in pairs[:3]:
        print(f"\n  PROMPT: {pair['prompt'][:140]}...")
        print(f"  OUTPUT: {pair['output'][:140]}...")

    return pairs


if __name__ == "__main__":
    generate_training_data()
