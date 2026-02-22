#!/usr/bin/env python3
"""
Generate SFT training data for the answer-extraction LLM (C4).

Creates prompt → extraction pairs in the format:
  Input:  [ANSWER] ... [TARGETS] ... [UNDEFINED] ...
  Output: [EXTRACT] resolved: elem=value | bonus: elem=value

These are used to fine-tune GPT-2 to extract structured info from user answers.
"""
from __future__ import annotations

import json
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

OUTPUT_PATH = "training_data/extractor_sft_data.jsonl"
MISSIONS_PATH = "training_data/missions.jsonl"

# Import the rich answer patterns from the RL episode generator
from generate_rl_episodes import ANSWER_PATTERNS, get_answer


# ── Additional compound answers that naturally mention multiple elements ──
COMPOUND_ANSWERS = [
    # Design + colors + branding
    {
        "answer": "We want a modern minimalist look with purple and white. We already have a logo.",
        "resolves": {
            "design_style": "modern minimalist",
            "color_preferences": "purple and white",
            "existing_branding": "Has existing branding assets",
        },
    },
    {
        "answer": "Clean and professional, blue tones, no existing brand assets — starting from scratch.",
        "resolves": {
            "design_style": "clean and professional",
            "color_preferences": "blue tones",
            "existing_branding": "No existing branding — starting fresh",
        },
    },
    {
        "answer": "Bold and colorful, think bright orange and teal. We have brand guidelines already.",
        "resolves": {
            "design_style": "bold and colorful",
            "color_preferences": "bright orange and teal",
            "existing_branding": "Has existing branding assets",
        },
    },
    # Audience + audience size
    {
        "answer": "Women 25-40 who love sustainable fashion. We have about 5000 email subscribers.",
        "resolves": {
            "target_audience": "Women 25-40 who love sustainable fashion",
            "existing_audience_size": "5000 email subscribers",
        },
    },
    {
        "answer": "Tech professionals, mainly developers. Our newsletter has 12k subscribers and we have 8k on Instagram.",
        "resolves": {
            "target_audience": "Tech professionals, mainly developers",
            "existing_audience_size": "12k subscribers",
        },
    },
    # Timeline + budget
    {
        "answer": "We need this done in 2 weeks, budget is around 3000 euros.",
        "resolves": {
            "timeline": "2 weeks",
            "budget": "3000 euros",
        },
    },
    {
        "answer": "No rush, 3 months is fine. Budget is flexible, probably 5-10K.",
        "resolves": {
            "timeline": "3 months",
            "budget": "5-10K",
        },
    },
    # Scope + deliverables + channels
    {
        "answer": "We need email campaigns and Instagram posts. Deliverables would be 5 email templates and 10 social graphics. Budget around 2K.",
        "resolves": {
            "campaign_channels": "email and Instagram",
            "deliverables": "5 email templates and 10 social graphics",
            "budget": "2K",
        },
    },
    # Offer + campaign goal
    {
        "answer": "The goal is to drive sales with a 20% discount code for new customers.",
        "resolves": {
            "campaign_goal": "drive sales",
            "offer_promotion": "20% discount code for new customers",
        },
    },
    # Tech + platform details
    {
        "answer": "We're on Shopify already and want to keep it. We need to integrate with Mailchimp for emails.",
        "resolves": {
            "tech_platform": "shopify",
            "email_platform": "Mailchimp",
            "integrations": "Mailchimp for emails",
        },
    },
    # Content + messaging
    {
        "answer": "The tone should be warm and friendly. The key message is that we make sustainable fashion accessible.",
        "resolves": {
            "messaging_tone": "warm and friendly",
            "key_message": "we make sustainable fashion accessible",
        },
    },
    # Full-scope answer
    {
        "answer": "WordPress site, modern design with dark theme, for our tech startup targeting developers. Need it in a month.",
        "resolves": {
            "tech_platform": "wordpress",
            "design_style": "modern, dark theme",
            "target_audience": "developers",
            "timeline": "a month",
        },
    },
    # Vague / minimal answers (should still resolve targets)
    {
        "answer": "Yeah that sounds good, go with it.",
        "resolves": {},
    },
    {
        "answer": "I trust your judgment on that one.",
        "resolves": {},
    },
    {
        "answer": "Not sure yet, probably standard.",
        "resolves": {},
    },
    # Email-specific compound
    {
        "answer": "Weekly newsletters plus automated welcome series. Using Klaviyo already. Around 3000 subscribers.",
        "resolves": {
            "email_types": "weekly newsletters plus automated welcome series",
            "email_platform": "Klaviyo",
            "existing_audience_size": "3000 subscribers",
            "automation_flows": "welcome series",
        },
    },
    # Mobile app compound
    {
        "answer": "iOS and Android, cross-platform with React Native. It's a fitness tracking app for gym enthusiasts.",
        "resolves": {
            "platform": "iOS and Android, cross-platform, React Native",
            "app_purpose": "fitness tracking app",
            "target_users": "gym enthusiasts",
        },
    },
]


def build_extractor_prompt(answer: str, targets: list[str],
                           undefined_elements: list[dict]) -> str:
    """Build the input prompt for the extractor model."""
    lines = []
    lines.append(f"[ANSWER] {answer}")

    targets_str = ", ".join(t.replace("_", " ") for t in targets)
    lines.append(f"[TARGETS] {targets_str}")

    if undefined_elements:
        undef_str = ", ".join(
            f"{e['name'].replace('_', ' ')} ({e['description'][:40]})"
            for e in undefined_elements[:10]
        )
        lines.append(f"[UNDEFINED] {undef_str}")

    lines.append("[EXTRACT]")
    return " ".join(lines)


def build_extraction_output(resolved: dict[str, str],
                            bonus: dict[str, str]) -> str:
    """Build the expected output for the extractor model."""
    parts = []

    if resolved:
        resolved_parts = [f"{k.replace('_', ' ')}={v}" for k, v in resolved.items()]
        parts.append("resolved: " + ", ".join(resolved_parts))
    else:
        parts.append("resolved: none")

    if bonus:
        bonus_parts = [f"{k.replace('_', ' ')}={v}" for k, v in bonus.items()]
        parts.append("bonus: " + ", ".join(bonus_parts))

    return " | ".join(parts)


def generate_training_data():
    """Generate training data for the extractor LLM."""
    missions = []
    with open(MISSIONS_PATH, "r") as f:
        for line in f:
            line = line.strip()
            if line:
                missions.append(json.loads(line))

    pairs = []

    # ── Strategy 1: Single-target answers from ANSWER_PATTERNS ──
    # For each element with known answer patterns, create examples
    # where that element is the target and the answer resolves it.
    for mission in missions:
        elements = mission["elements"]
        for _ in range(30):
            # Pick 1-2 random target elements
            num_targets = random.choice([1, 1, 1, 2])
            target_indices = random.sample(
                range(len(elements)), min(num_targets, len(elements))
            )
            targets = [elements[i] for i in target_indices]
            target_names = [t["name"] for t in targets]

            # Get answer for primary target
            primary_answer = get_answer(targets[0]["name"])

            # If multiple targets, sometimes combine answers
            if len(targets) > 1 and random.random() < 0.6:
                second_answer = get_answer(targets[1]["name"])
                answer = f"{primary_answer}. Also, {second_answer.lower()}"
            else:
                answer = primary_answer

            # Build resolved dict — the target elements are resolved
            resolved = {}
            for t in targets:
                if t["name"] in ANSWER_PATTERNS:
                    # Use the actual answer text as the value
                    resolved[t["name"]] = get_answer(t["name"])
                else:
                    # For elements without specific patterns, use the raw answer
                    resolved[t["name"]] = answer.strip()

            # Build undefined elements (everything else)
            undefined = [
                e for e in elements
                if e["name"] not in target_names
            ]

            # Sometimes add bonus elements (20% chance)
            bonus = {}
            if random.random() < 0.2 and undefined:
                bonus_elem = random.choice(undefined)
                if bonus_elem["name"] in ANSWER_PATTERNS:
                    bonus[bonus_elem["name"]] = get_answer(bonus_elem["name"])

            prompt = build_extractor_prompt(answer, target_names, undefined)
            output = build_extraction_output(resolved, bonus)

            pairs.append({
                "text": f"{prompt} {output}",
                "prompt": prompt,
                "output": output,
                "targets": target_names,
                "category": mission["category"],
            })

    # ── Strategy 2: Compound answers that resolve multiple elements ──
    for mission in missions:
        elements = mission["elements"]
        element_names = {e["name"] for e in elements}

        for compound in COMPOUND_ANSWERS:
            # Check if any resolved elements exist in this mission
            matching = {
                k: v for k, v in compound["resolves"].items()
                if k in element_names
            }
            if not matching:
                continue

            # Pick targets: usually a subset of what the answer resolves
            target_names = list(matching.keys())[:2]

            # Split into resolved (targets) and bonus (extras)
            resolved = {k: v for k, v in matching.items() if k in target_names}
            bonus = {k: v for k, v in matching.items() if k not in target_names}

            # If no specific extraction, the target is still resolved with raw text
            if not resolved and target_names:
                resolved = {t: compound["answer"].strip() for t in target_names}

            undefined = [
                e for e in elements
                if e["name"] not in target_names
            ]

            prompt = build_extractor_prompt(
                compound["answer"], target_names, undefined
            )
            output = build_extraction_output(resolved, bonus)

            pairs.append({
                "text": f"{prompt} {output}",
                "prompt": prompt,
                "output": output,
                "targets": target_names,
                "category": mission["category"],
            })

    # ── Strategy 3: Vague/minimal answers ──
    # User gives a short or vague answer — still resolves targets with raw text
    vague_answers = [
        "Yes, that works for me.",
        "Sounds good, go ahead with that.",
        "I like that idea, let's do it.",
        "Not sure about the details, but generally yes.",
        "Whatever you think is best.",
        "Hmm, I need to think about that more.",
        "Yeah, something like that.",
        "Definitely, that's what we want.",
        "I agree, that direction sounds right.",
        "Keep it simple, nothing too fancy.",
        "Sure, standard approach is fine.",
        "Let's go with your recommendation on that.",
    ]

    for mission in missions:
        elements = mission["elements"]
        for _ in range(10):
            target_idx = random.randint(0, len(elements) - 1)
            target = elements[target_idx]
            answer = random.choice(vague_answers)

            undefined = [e for e in elements if e["name"] != target["name"]]

            # Vague answers still resolve the target with the raw text
            resolved = {target["name"]: answer.strip()}

            prompt = build_extractor_prompt(
                answer, [target["name"]], undefined
            )
            output = build_extraction_output(resolved, {})

            pairs.append({
                "text": f"{prompt} {output}",
                "prompt": prompt,
                "output": output,
                "targets": [target["name"]],
                "category": mission["category"],
            })

    # ── Strategy 4: Multi-element cluster answers ──
    # Answers that naturally cover a group of related elements
    for mission in missions:
        elements = mission["elements"]
        for _ in range(15):
            # Pick 2-3 elements
            num = min(random.randint(2, 3), len(elements))
            chosen = random.sample(elements, num)
            target_names = [e["name"] for e in chosen]

            # Build a combined answer
            answer_parts = []
            resolved = {}
            for elem in chosen:
                ans = get_answer(elem["name"])
                answer_parts.append(ans)
                resolved[elem["name"]] = ans

            # Join parts naturally
            if len(answer_parts) == 2:
                answer = f"{answer_parts[0]}. And for the other thing, {answer_parts[1].lower()}"
            else:
                answer = ". ".join(answer_parts)

            undefined = [e for e in elements if e["name"] not in target_names]

            prompt = build_extractor_prompt(answer, target_names, undefined)
            output = build_extraction_output(resolved, {})

            pairs.append({
                "text": f"{prompt} {output}",
                "prompt": prompt,
                "output": output,
                "targets": target_names,
                "category": mission["category"],
            })

    # Shuffle all pairs
    random.shuffle(pairs)

    # Write output
    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    with open(OUTPUT_PATH, "w") as f:
        for pair in pairs:
            f.write(json.dumps(pair) + "\n")

    print(f"✅ Generated {len(pairs)} extractor SFT training examples")
    print(f"📄 Saved to: {OUTPUT_PATH}")
    print(f"📊 Categories: {len(missions)}")

    # Stats
    single = sum(1 for p in pairs if len(p["targets"]) == 1)
    multi = sum(1 for p in pairs if len(p["targets"]) > 1)
    print(f"   Single-target: {single}, Multi-target: {multi}")

    # Show examples
    print("\n📝 Sample training examples:")
    for pair in pairs[:3]:
        print(f"\n  PROMPT: {pair['prompt'][:140]}...")
        print(f"  OUTPUT: {pair['output'][:120]}")

    return pairs


if __name__ == "__main__":
    generate_training_data()
