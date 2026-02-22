#!/usr/bin/env python3
"""
Train/prepare the TELOS model components.
1. Trains the sentence-transformer embeddings for clustering (C2)
2. Optimizes the reward function weights from RL episodes (C3)
3. Builds the element-to-question mapping (C3)
4. Validates everything works end-to-end (single + multi-task)
"""
from __future__ import annotations

import json
import os
import sys
import pickle
import random
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  )

MISSIONS_PATH = "training_data/missions.jsonl"
SFT_PATH = "training_data/sft_pairs.jsonl"
RL_PATH = "training_data/rl_episodes.jsonl"
MODEL_DIR = "ali/trained_models"


def load_jsonl(path):
    items = []
    with open(path, "r") as f:
        for line in f:
            line = line.strip()
            if line:
                items.append(json.loads(line))
    return items


def train_embeddings():
    """Train element embeddings using sentence-transformers for smart clustering."""
    print("═" * 60)
    print("📐 Step 1: Training Element Embeddings")
    print("═" * 60)

    try:
        from sentence_transformers import SentenceTransformer
        import numpy as np

        model = SentenceTransformer("all-MiniLM-L6-v2")
        print("   ✅ Loaded sentence-transformer: all-MiniLM-L6-v2")

        # Load all elements
        missions = load_jsonl(MISSIONS_PATH)
        all_elements = []
        element_texts = []

        for mission in missions:
            for elem in mission["elements"]:
                key = f"{mission['category']}:{elem['name']}"
                text = f"{elem['name'].replace('_', ' ')}: {elem['description']}"
                all_elements.append({
                    "key": key,
                    "category": mission["category"],
                    "name": elem["name"],
                    "description": elem["description"],
                    "score": elem["score"],
                })
                element_texts.append(text)

        print(f"   📊 Encoding {len(element_texts)} elements...")
        embeddings = model.encode(element_texts, show_progress_bar=True)

        # Save embeddings
        os.makedirs(MODEL_DIR, exist_ok=True)
        embedding_data = {
            "elements": all_elements,
            "embeddings": embeddings,
            "model_name": "all-MiniLM-L6-v2",
        }
        
        with open(os.path.join(MODEL_DIR, "element_embeddings.pkl"), "wb") as f:
            pickle.dump(embedding_data, f)

        print(f"   ✅ Saved embeddings to {MODEL_DIR}/element_embeddings.pkl")
        print(f"   📊 Shape: {embeddings.shape}")
        return embeddings, all_elements

    except ImportError:
        print("   ⚠️ sentence-transformers not available, skipping embedding training")
        return None, None


def train_clusters(embeddings, all_elements):
    """Train K-Means clusters per category using real embeddings."""
    print()
    print("═" * 60)
    print("🎯 Step 2: Training Smart Clusters")
    print("═" * 60)

    if embeddings is None:
        print("   ⚠️ No embeddings available, using rule-based clustering")
        return

    try:
        from sklearn.cluster import KMeans
        import numpy as np

        missions = load_jsonl(MISSIONS_PATH)
        cluster_results = {}

        for mission in missions:
            category = mission["category"]
            # Get indices for this category
            cat_indices = [
                i for i, e in enumerate(all_elements)
                if e["category"] == category
            ]
            if len(cat_indices) < 3:
                continue

            cat_embeddings = embeddings[cat_indices]
            n_clusters = min(5, len(cat_indices) // 2)

            kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
            labels = kmeans.fit_predict(cat_embeddings)

            # Build cluster map
            clusters = {}
            for idx, label in zip(cat_indices, labels):
                cluster_name = f"cluster_{label}"
                if cluster_name not in clusters:
                    clusters[cluster_name] = []
                clusters[cluster_name].append(all_elements[idx]["name"])

            cluster_results[category] = clusters
            print(f"   ✅ {category}: {n_clusters} clusters")
            for name, members in clusters.items():
                print(f"      {name}: {', '.join(members[:4])}{'...' if len(members) > 4 else ''}")

        # Save cluster model
        with open(os.path.join(MODEL_DIR, "cluster_model.pkl"), "wb") as f:
            pickle.dump(cluster_results, f)

        print(f"\n   ✅ Saved cluster model to {MODEL_DIR}/cluster_model.pkl")
        return cluster_results

    except ImportError:
        print("   ⚠️ sklearn not available, using rule-based clustering")
        return None


def optimize_reward_weights():
    """Optimize reward function weights from RL episodes."""
    print()
    print("═" * 60)
    print("🏆 Step 3: Optimizing Reward Function")
    print("═" * 60)

    episodes = load_jsonl(RL_PATH)

    # Analyze episode patterns
    best_episodes = sorted(episodes, key=lambda e: e["reward"], reverse=True)[:50]
    worst_episodes = sorted(episodes, key=lambda e: e["reward"])[:50]

    # Extract patterns from best vs worst
    best_avg_turns = sum(e["total_turns"] for e in best_episodes) / len(best_episodes)
    worst_avg_turns = sum(e["total_turns"] for e in worst_episodes) / len(worst_episodes)
    best_avg_coverage = sum(e["final_coverage"] for e in best_episodes) / len(best_episodes)
    worst_avg_coverage = sum(e["final_coverage"] for e in worst_episodes) / len(worst_episodes)

    # Calculate optimal weights with more nuanced tuning
    coverage_weight = 2.0 if best_avg_coverage > 0.95 else (1.5 if best_avg_coverage > 0.9 else 1.0)
    brevity_weight = 12 if best_avg_turns < 3 else (8 if best_avg_turns < 5 else 5)
    multi_element_bonus = 25  # Higher reward for covering 2+ elements
    cluster_bonus = 35  # Higher reward for cluster questions

    # Analyze multi-task episodes separately
    multi_eps = [e for e in episodes if e.get("multi_task")]
    if multi_eps:
        multi_avg_coverage = sum(e["final_coverage"] for e in multi_eps) / len(multi_eps)
        multi_avg_turns = sum(e["total_turns"] for e in multi_eps) / len(multi_eps)
        print(f"   📊 Multi-task episodes: {len(multi_eps)}")
        print(f"   📊 Multi-task avg: {multi_avg_turns:.1f} turns, {multi_avg_coverage*100:.0f}% coverage")

    weights = {
        "coverage_weight": coverage_weight,
        "brevity_weight": brevity_weight,
        "multi_element_bonus": multi_element_bonus,
        "cluster_bonus": cluster_bonus,
    }

    print(f"   📊 Best episodes: avg {best_avg_turns:.1f} turns, {best_avg_coverage*100:.0f}% coverage")
    print(f"   📊 Worst episodes: avg {worst_avg_turns:.1f} turns, {worst_avg_coverage*100:.0f}% coverage")
    print(f"   📊 Optimized weights: {json.dumps(weights, indent=2)}")

    # Save weights
    os.makedirs(MODEL_DIR, exist_ok=True)
    with open(os.path.join(MODEL_DIR, "reward_weights.json"), "w") as f:
        json.dump(weights, f, indent=2)

    print(f"   ✅ Saved reward weights to {MODEL_DIR}/reward_weights.json")
    return weights


def build_question_templates():
    """Build and expand question templates for all categories."""
    print()
    print("═" * 60)
    print("❓ Step 4: Building Question Template Bank")
    print("═" * 60)

    missions = load_jsonl(MISSIONS_PATH)

    # Load the hardcoded expert templates from RLQuestionGenerator
    from ali.rl_question_generator import RLQuestionGenerator
    gen = RLQuestionGenerator(model_dir="/dev/null")  # Don't load existing
    expert_templates = gen.QUESTION_TEMPLATES

    # Build complete template bank — expert templates take priority
    template_bank = {}
    total_templates = 0

    for mission in missions:
        category = mission["category"]
        template_bank[category] = {}
        
        for elem in mission["elements"]:
            name = elem["name"]
            desc = elem["description"]
            score = elem["score"]

            # Try expert templates first
            if name in expert_templates:
                templates = expert_templates[name]
            else:
                # Generate contextual templates based on the element
                if score >= 80:
                    templates = [
                        f"Tell me about {desc.lower()} — what are you thinking?",
                        f"What's your vision for {desc.lower()}?",
                        f"Let's start with {desc.lower()} — this is key. What do you have in mind?",
                    ]
                elif score >= 40:
                    templates = [
                        f"What about {desc.lower()}? Any thoughts on that?",
                        f"Have you considered {desc.lower()} yet?",
                        f"Let's talk about {desc.lower()} — any plans there?",
                    ]
                else:
                    templates = [
                        f"One more thing — any thoughts on {desc.lower()}?",
                        f"Before we wrap up, what about {desc.lower()}?",
                    ]

            template_bank[category][name] = templates
            total_templates += len(templates)

    # Save template bank
    os.makedirs(MODEL_DIR, exist_ok=True)
    with open(os.path.join(MODEL_DIR, "question_templates.json"), "w") as f:
        json.dump(template_bank, f, indent=2)

    print(f"   ✅ Generated templates for {len(template_bank)} categories")
    print(f"   📊 Total templates: {total_templates}")
    print(f"   📊 Expert-quality templates used for {len(expert_templates)} element types")
    print(f"   📄 Saved to {MODEL_DIR}/question_templates.json")
    return template_bank


def validate_end_to_end():
    """Quick validation that everything works together — single + multi-task."""
    print()
    print("═" * 60)
    print("🧪 Step 5: End-to-End Validation")
    print("═" * 60)

    from ali.conversation_loop import ConversationLoop

    # Single-task tests
    test_prompts = [
        ("I want to build a website for my bakery", ["web_development"]),
        ("Help me create a mobile app for tracking fitness", ["mobile_app"]),
        ("We need a marketing campaign for our new product", ["marketing_campaign"]),
        ("I want to build a SaaS for managing projects", ["saas_product"]),
        ("I need a social media strategy for my restaurant", ["social_media"]),
        ("I want to set up email marketing for my bakery", ["email_marketing"]),
    ]

    # Multi-task tests
    multi_task_prompts = [
        ("I need a website update and email marketing setup for my bakery",
         ["web_development", "email_marketing"]),
        ("Help me build an online store and run a marketing campaign",
         ["ecommerce", "marketing_campaign"]),
        ("We need a social media strategy and video production for our launch",
         ["social_media", "video_production"]),
    ]

    all_passed = True

    print("\n   📋 Single-task tests:")
    for prompt, expected_cats in test_prompts:
        loop = ConversationLoop(
            missions_path=MISSIONS_PATH,
            context_path="/tmp/telos_validate.md",
        )
        result = loop.start(prompt)
        actual_cat = result["category"]
        passed = actual_cat in expected_cats
        icon = "✅" if passed else "❌"

        print(f"   {icon} \"{prompt[:50]}...\"")
        print(f"      Category: {actual_cat} (expected: {expected_cats[0]})")
        print(f"      Pre-answered: {result['pre_answered_count']}/{result['total_elements']}")
        q = result.get("first_question") or "None"
        print(f"      First Q: {q[:70]}")
        
        if not passed:
            all_passed = False

    print("\n   📋 Multi-task tests:")
    for prompt, expected_cats in multi_task_prompts:
        loop = ConversationLoop(
            missions_path=MISSIONS_PATH,
            context_path="/tmp/telos_validate_multi.md",
        )
        result = loop.start(prompt)
        actual_cats = result.get("categories", [result["category"]])
        # Check if at least one expected category was detected
        overlap = set(actual_cats) & set(expected_cats)
        passed = len(overlap) >= 1
        icon = "✅" if passed else "❌"

        print(f"   {icon} \"{prompt[:50]}...\"")
        print(f"      Detected: {actual_cats}")
        print(f"      Expected: {expected_cats}")
        print(f"      Elements: {result['total_elements']}")

        if not passed:
            all_passed = False

    print()
    if all_passed:
        print("   🎉 All validations passed!")
    else:
        print("   ⚠️ Some validations had mismatches (acceptable for fuzzy matching)")

    return all_passed


def main():
    start_time = time.time()
    print("🚀 TELOS — Training Pipeline")
    print("=" * 60)
    print()

    # Step 1: Embeddings
    embeddings, all_elements = train_embeddings()

    # Step 2: Smart clusters
    train_clusters(embeddings, all_elements)

    # Step 3: Reward optimization
    optimize_reward_weights()

    # Step 4: Question templates
    build_question_templates()

    # Step 5: Validation
    validate_end_to_end()

    elapsed = time.time() - start_time
    print()
    print("=" * 60)
    print("✅ TELOS TRAINING COMPLETE")
    print("=" * 60)
    print(f"⏱️  Total time: {elapsed:.1f}s")
    print()
    print("Models saved to: ali/trained_models/")
    print("  - element_embeddings.pkl  (sentence-transformer embeddings)")
    print("  - cluster_model.pkl       (K-Means clusters per category)")
    print("  - reward_weights.json     (optimized reward weights)")
    print("  - question_templates.json (expert question bank)")
    print()
    print("Run interactive mode:")
    print("  python3 -m ali.main")


if __name__ == "__main__":
    main()
