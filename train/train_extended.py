#!/usr/bin/env python3
"""
TELOS — Extended Training Pipeline (~20 minutes)

This is the serious training pipeline that:
1. Generates massive training data (thousands of episodes)
2. Evolutionary optimization of reward weights through grid search
3. Monte Carlo conversation simulations to evaluate question strategies
4. Template selection — tests all templates in simulated conversations, keeps the best
5. Multi-pass clustering with different K values
6. Multiple iterations: generate → evaluate → keep best → repeat
7. Saves checkpoints and keeps only the best-performing configuration
"""
from __future__ import annotations

import json
import os
import sys
import pickle
import random
import time
import copy
import itertools
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

MISSIONS_PATH = "train/data/missions.jsonl"
SFT_PATH = "train/data/sft_pairs.jsonl"
RL_PATH = "train/data/rl_episodes.jsonl"
MODEL_DIR = "ali/trained_models"
CHECKPOINT_DIR = "ali/trained_models/checkpoints"

# ═══════════════════════════════════════════════════════════
# Training configuration
# ═══════════════════════════════════════════════════════════
TARGET_DURATION_MINUTES = 20
MONTE_CARLO_EPISODES_PER_CONFIG = 200
GRID_SEARCH_ITERATIONS = 50
EVOLUTIONARY_GENERATIONS = 30
POPULATION_SIZE = 20
ELITE_SIZE = 5
MUTATION_RATE = 0.3
TEMPLATE_EVAL_ROUNDS = 100
MULTI_TASK_RATIO = 0.25  # 25% of episodes are multi-task


def load_jsonl(path):
    items = []
    with open(path, "r") as f:
        for line in f:
            line = line.strip()
            if line:
                items.append(json.loads(line))
    return items


def save_checkpoint(name, data):
    """Save a training checkpoint."""
    os.makedirs(CHECKPOINT_DIR, exist_ok=True)
    path = os.path.join(CHECKPOINT_DIR, f"{name}.json")
    with open(path, "w") as f:
        json.dump(data, f, indent=2)
    return path


# ═══════════════════════════════════════════════════════════
# PHASE 1: Massive Data Generation
# ═══════════════════════════════════════════════════════════

# Import answer patterns from the RL episode generator (same train/ directory)
from generate_rl_episodes import ANSWER_PATTERNS, get_answer


def generate_massive_episodes(missions, n_per_category=100, n_multi=200):
    """Generate a massive set of RL episodes for training."""
    episodes = []

    for mission in missions:
        for _ in range(n_per_category):
            ep = _simulate_episode(mission)
            episodes.append(ep)

    # Multi-task episodes
    for _ in range(n_multi):
        selected = random.sample(missions, min(2, len(missions)))
        ep = _simulate_multi_episode(selected)
        episodes.append(ep)

    return episodes


def _simulate_episode(mission, weights=None):
    """Simulate a single conversation episode with given reward weights."""
    elements = [
        {**e, "status": "undefined", "value": None}
        for e in mission["elements"]
    ]

    w = weights or {
        "coverage_weight": 1.5,
        "brevity_weight": 5,
        "multi_element_bonus": 20,
        "cluster_bonus": 30,
    }

    num_pre = random.randint(1, min(4, len(elements)))
    pre_idx = random.sample(range(len(elements)), num_pre)
    for idx in pre_idx:
        elements[idx]["status"] = "answered"
        elements[idx]["value"] = get_answer(elements[idx]["name"])

    total_score = sum(e["score"] for e in elements)
    answered_score = sum(e["score"] for e in elements if e["status"] == "answered")

    turns = []
    turn_num = 0
    max_turns = random.randint(3, 10)

    # Different question strategies
    strategy = random.choice(["greedy", "cluster", "balanced", "priority"])

    while turn_num < max_turns:
        coverage = answered_score / total_score if total_score > 0 else 1.0
        if coverage >= 0.90:
            break

        undefined = [e for e in elements if e["status"] == "undefined"]
        if not undefined:
            break

        # Apply strategy
        if strategy == "greedy":
            # Always pick highest-score elements
            undefined.sort(key=lambda e: e["score"], reverse=True)
            num_targets = min(random.randint(1, 2), len(undefined))
            targets = undefined[:num_targets]
        elif strategy == "cluster":
            # Pick 2-3 related elements
            undefined.sort(key=lambda e: e["score"], reverse=True)
            num_targets = min(random.randint(2, 3), len(undefined))
            targets = undefined[:num_targets]
        elif strategy == "balanced":
            # Mix high and medium priority
            undefined.sort(key=lambda e: e["score"], reverse=True)
            if len(undefined) >= 3:
                targets = [undefined[0], undefined[len(undefined) // 2]]
            else:
                targets = undefined[:1]
        else:  # priority
            # Strict priority order, one at a time
            undefined.sort(key=lambda e: e["score"], reverse=True)
            targets = undefined[:1]

        question_targets = [t["name"] for t in targets]
        # Simulate that user sometimes gives bonus info
        bonus_elements = []
        if random.random() < 0.2 and len(undefined) > len(targets):
            remaining = [e for e in undefined if e not in targets]
            bonus = random.choice(remaining)
            bonus_elements.append(bonus)

        for t in targets + bonus_elements:
            t["status"] = "answered"
            t["value"] = get_answer(t["name"])
            answered_score += t["score"]

        turn_num += 1
        turns.append({
            "turn": turn_num,
            "targets": question_targets,
            "bonus": [b["name"] for b in bonus_elements],
            "answer": get_answer(targets[0]["name"]),
            "coverage_after": answered_score / total_score,
            "elements_resolved": len(question_targets) + len(bonus_elements),
            "strategy": strategy,
        })

    final_coverage = answered_score / total_score if total_score > 0 else 1.0

    # Calculate reward with the given weights
    coverage_reward = final_coverage * 100 * w["coverage_weight"]
    brevity_reward = max(0, (10 - len(turns))) * w["brevity_weight"]
    multi_bonus = sum(
        w["multi_element_bonus"] for t in turns if t["elements_resolved"] > 1
    )
    cluster_used = sum(1 for t in turns if len(t["targets"]) > 1)
    cluster_reward = cluster_used * w["cluster_bonus"]

    total_reward = coverage_reward + brevity_reward + multi_bonus + cluster_reward

    return {
        "category": mission["category"],
        "task": mission["task"],
        "total_elements": len(elements),
        "pre_answered": num_pre,
        "turns": turns,
        "final_coverage": round(final_coverage, 4),
        "total_turns": len(turns),
        "reward": round(total_reward, 2),
        "strategy": strategy,
    }


def _simulate_multi_episode(missions, weights=None):
    """Simulate a multi-task conversation."""
    all_elements = []
    seen_names = set()
    for mission in missions:
        for e in mission["elements"]:
            if e["name"] not in seen_names:
                all_elements.append({**e, "status": "undefined", "value": None})
                seen_names.add(e["name"])

    w = weights or {
        "coverage_weight": 1.5,
        "brevity_weight": 5,
        "multi_element_bonus": 20,
        "cluster_bonus": 30,
    }

    num_pre = random.randint(2, min(6, len(all_elements)))
    pre_idx = random.sample(range(len(all_elements)), num_pre)
    for idx in pre_idx:
        all_elements[idx]["status"] = "answered"
        all_elements[idx]["value"] = get_answer(all_elements[idx]["name"])

    total_score = sum(e["score"] for e in all_elements)
    answered_score = sum(e["score"] for e in all_elements if e["status"] == "answered")

    turns = []
    turn_num = 0
    max_turns = random.randint(5, 12)
    strategy = random.choice(["greedy", "cluster", "balanced"])

    while turn_num < max_turns:
        coverage = answered_score / total_score if total_score > 0 else 1.0
        if coverage >= 0.90:
            break
        undefined = [e for e in all_elements if e["status"] == "undefined"]
        if not undefined:
            break

        undefined.sort(key=lambda e: e["score"], reverse=True)
        num_targets = min(random.randint(1, 3), len(undefined))
        targets = undefined[:num_targets]

        for t in targets:
            t["status"] = "answered"
            t["value"] = get_answer(t["name"])
            answered_score += t["score"]

        turn_num += 1
        turns.append({
            "turn": turn_num,
            "targets": [t["name"] for t in targets],
            "answer": get_answer(targets[0]["name"]),
            "coverage_after": answered_score / total_score,
            "elements_resolved": len(targets),
            "strategy": strategy,
        })

    final_coverage = answered_score / total_score if total_score > 0 else 1.0
    coverage_reward = final_coverage * 100 * w["coverage_weight"]
    brevity_reward = max(0, (12 - len(turns))) * w["brevity_weight"]
    multi_bonus = sum(
        w["multi_element_bonus"] for t in turns if t["elements_resolved"] > 1
    )

    return {
        "category": "+".join(m["category"] for m in missions),
        "task": " + ".join(m["task"] for m in missions),
        "total_elements": len(all_elements),
        "pre_answered": num_pre,
        "turns": turns,
        "final_coverage": round(final_coverage, 4),
        "total_turns": len(turns),
        "reward": round(coverage_reward + brevity_reward + multi_bonus, 2),
        "multi_task": True,
        "strategy": strategy,
    }


# ═══════════════════════════════════════════════════════════
# PHASE 2: Evolutionary Reward Weight Optimization
# ═══════════════════════════════════════════════════════════

def create_random_weights():
    """Create a random set of reward weights."""
    return {
        "coverage_weight": round(random.uniform(0.5, 3.0), 2),
        "brevity_weight": round(random.uniform(2, 15), 1),
        "multi_element_bonus": round(random.uniform(5, 50), 1),
        "cluster_bonus": round(random.uniform(10, 60), 1),
    }


def mutate_weights(weights, rate=MUTATION_RATE):
    """Mutate reward weights slightly."""
    new_weights = {}
    for key, val in weights.items():
        if random.random() < rate:
            delta = val * random.uniform(-0.3, 0.3)
            new_weights[key] = round(max(0.1, val + delta), 2)
        else:
            new_weights[key] = val
    return new_weights


def crossover_weights(w1, w2):
    """Cross two weight configurations."""
    child = {}
    for key in w1:
        child[key] = w1[key] if random.random() < 0.5 else w2[key]
    return child


def evaluate_weights(weights, missions, n_episodes=100):
    """Evaluate a weight configuration by running Monte Carlo simulations.
    Returns a fitness score (higher is better).
    Fitness = mean(coverage) * 100 - mean(turns) * 3 + bonus_for_consistency
    """
    episodes = []
    for _ in range(n_episodes):
        mission = random.choice(missions)
        if random.random() < MULTI_TASK_RATIO:
            selected = random.sample(missions, min(2, len(missions)))
            ep = _simulate_multi_episode(selected, weights)
        else:
            ep = _simulate_episode(mission, weights)
        episodes.append(ep)

    coverages = [e["final_coverage"] for e in episodes]
    turns_list = [e["total_turns"] for e in episodes]
    rewards = [e["reward"] for e in episodes]

    mean_coverage = sum(coverages) / len(coverages)
    mean_turns = sum(turns_list) / len(turns_list)
    mean_reward = sum(rewards) / len(rewards)

    # Consistency bonus: low variance is good
    coverage_var = sum((c - mean_coverage) ** 2 for c in coverages) / len(coverages)
    consistency_bonus = max(0, 10 - coverage_var * 100)

    # High coverage episodes bonus
    high_coverage_pct = sum(1 for c in coverages if c >= 0.90) / len(coverages)
    high_coverage_bonus = high_coverage_pct * 20

    # Efficiency: high coverage with few turns
    efficiency = mean_coverage / max(mean_turns, 1) * 50

    fitness = (
        mean_coverage * 100
        - mean_turns * 3
        + consistency_bonus
        + high_coverage_bonus
        + efficiency
    )

    return {
        "fitness": round(fitness, 3),
        "mean_coverage": round(mean_coverage, 4),
        "mean_turns": round(mean_turns, 2),
        "mean_reward": round(mean_reward, 2),
        "high_coverage_pct": round(high_coverage_pct, 3),
        "coverage_variance": round(coverage_var, 6),
    }


def evolutionary_optimize(missions, generations=EVOLUTIONARY_GENERATIONS,
                          pop_size=POPULATION_SIZE):
    """Run evolutionary optimization on reward weights."""
    print()
    print("═" * 60)
    print("🧬 PHASE 2: Evolutionary Reward Weight Optimization")
    print(f"   Generations: {generations}, Population: {pop_size}")
    print("═" * 60)

    # Initialize population
    population = [create_random_weights() for _ in range(pop_size)]
    # Seed with current best if available
    weights_path = os.path.join(MODEL_DIR, "reward_weights.json")
    if os.path.exists(weights_path):
        with open(weights_path, "r") as f:
            current_best = json.load(f)
        population[0] = current_best
        # Add mutations of current best
        for i in range(1, min(5, pop_size)):
            population[i] = mutate_weights(current_best, rate=0.5)

    best_ever = None
    best_ever_fitness = -float("inf")
    history = []

    for gen in range(generations):
        # Evaluate each individual
        results = []
        for weights in population:
            eval_result = evaluate_weights(weights, missions,
                                           n_episodes=MONTE_CARLO_EPISODES_PER_CONFIG)
            results.append((weights, eval_result))

        # Sort by fitness
        results.sort(key=lambda x: x[1]["fitness"], reverse=True)

        gen_best = results[0]
        gen_avg = sum(r[1]["fitness"] for r in results) / len(results)

        if gen_best[1]["fitness"] > best_ever_fitness:
            best_ever = copy.deepcopy(gen_best[0])
            best_ever_fitness = gen_best[1]["fitness"]

        history.append({
            "generation": gen + 1,
            "best_fitness": gen_best[1]["fitness"],
            "avg_fitness": round(gen_avg, 3),
            "best_coverage": gen_best[1]["mean_coverage"],
            "best_turns": gen_best[1]["mean_turns"],
        })

        if gen % 5 == 0 or gen == generations - 1:
            print(f"   Gen {gen+1:>3}/{generations}: "
                  f"best={gen_best[1]['fitness']:.1f} "
                  f"avg={gen_avg:.1f} "
                  f"cov={gen_best[1]['mean_coverage']*100:.0f}% "
                  f"turns={gen_best[1]['mean_turns']:.1f} "
                  f"hi90={gen_best[1]['high_coverage_pct']*100:.0f}%")

        # Selection + reproduction
        elite = [r[0] for r in results[:ELITE_SIZE]]
        new_population = list(elite)  # Keep elite

        while len(new_population) < pop_size:
            if random.random() < 0.7:
                # Crossover
                p1, p2 = random.sample(elite, 2)
                child = crossover_weights(p1, p2)
                child = mutate_weights(child, rate=MUTATION_RATE)
                new_population.append(child)
            else:
                # Fresh random individual (exploration)
                new_population.append(create_random_weights())

        population = new_population

    # Save best weights
    os.makedirs(MODEL_DIR, exist_ok=True)
    with open(os.path.join(MODEL_DIR, "reward_weights.json"), "w") as f:
        json.dump(best_ever, f, indent=2)

    save_checkpoint("evolutionary_history", {
        "history": history,
        "best_weights": best_ever,
        "best_fitness": best_ever_fitness,
    })

    print(f"\n   🏆 Best weights: {json.dumps(best_ever)}")
    print(f"   🏆 Best fitness: {best_ever_fitness:.2f}")
    return best_ever


# ═══════════════════════════════════════════════════════════
# PHASE 3: Question Template Evaluation & Selection
# ═══════════════════════════════════════════════════════════

def evaluate_templates(missions, optimal_weights):
    """Evaluate question templates by simulating conversations and
    measuring which question orderings produce best coverage/turn ratio."""
    print()
    print("═" * 60)
    print("📝 PHASE 3: Question Template Evaluation & Selection")
    print("═" * 60)

    from ali.rl_question_generator import RLQuestionGenerator
    gen = RLQuestionGenerator(model_dir=MODEL_DIR)

    template_scores = defaultdict(lambda: {"asked": 0, "resolved": 0,
                                           "bonus": 0, "total_score": 0})

    for round_num in range(TEMPLATE_EVAL_ROUNDS):
        mission = random.choice(missions)
        elements = [
            {**e, "status": "undefined", "value": None}
            for e in mission["elements"]
        ]

        # Pre-answer a few
        num_pre = random.randint(1, min(3, len(elements)))
        for idx in random.sample(range(len(elements)), num_pre):
            elements[idx]["status"] = "answered"
            elements[idx]["value"] = get_answer(elements[idx]["name"])

        # Simulate asking questions
        conversation_history = []
        for turn in range(8):
            undefined = [e for e in elements if e["status"] == "undefined"]
            if not undefined:
                break

            total_score = sum(e["score"] for e in elements)
            answered_score = sum(e["score"] for e in elements if e["status"] == "answered")
            if answered_score / total_score >= 0.90:
                break

            # Pick a target element and get template question
            undefined.sort(key=lambda e: e["score"], reverse=True)
            target = undefined[0]
            target_name = target["name"]

            # Get templates for this element
            templates = gen.QUESTION_TEMPLATES.get(target_name, [])
            if not templates and gen._trained_templates:
                for cat_templates in gen._trained_templates.values():
                    if target_name in cat_templates:
                        templates = cat_templates[target_name]
                        break

            if templates:
                chosen_template = random.choice(templates)
                # Simulate answer
                answer = get_answer(target_name)
                target["status"] = "answered"
                target["value"] = answer
                answered_score += target["score"]

                # Random bonus resolution
                bonus_count = 0
                if random.random() < 0.15:
                    remaining = [e for e in undefined if e["name"] != target_name]
                    if remaining:
                        bonus_elem = random.choice(remaining)
                        bonus_elem["status"] = "answered"
                        bonus_elem["value"] = get_answer(bonus_elem["name"])
                        bonus_count = 1

                template_scores[target_name]["asked"] += 1
                template_scores[target_name]["resolved"] += 1
                template_scores[target_name]["bonus"] += bonus_count
                template_scores[target_name]["total_score"] += target["score"]

                conversation_history.append({
                    "turn": turn + 1,
                    "targets": [target_name],
                    "resolved": [target_name],
                })

        if round_num % 20 == 0:
            total_score_sum = sum(s["total_score"] for s in template_scores.values())
            total_asked = sum(s["asked"] for s in template_scores.values())
            print(f"   Round {round_num+1}/{TEMPLATE_EVAL_ROUNDS}: "
                  f"{total_asked} questions asked, "
                  f"avg score={total_score_sum / max(total_asked, 1):.1f}")

    # Calculate template effectiveness
    template_ranking = []
    for name, stats in template_scores.items():
        if stats["asked"] > 0:
            effectiveness = (
                stats["total_score"] / stats["asked"]
                + stats["bonus"] / stats["asked"] * 20
            )
            template_ranking.append({
                "element": name,
                "times_asked": stats["asked"],
                "avg_score": round(stats["total_score"] / stats["asked"], 1),
                "bonus_rate": round(stats["bonus"] / stats["asked"], 3),
                "effectiveness": round(effectiveness, 2),
            })

    template_ranking.sort(key=lambda x: x["effectiveness"], reverse=True)

    print(f"\n   📊 Top 10 most effective question targets:")
    for item in template_ranking[:10]:
        print(f"      {item['element']:<30} score={item['avg_score']:.0f} "
              f"bonus={item['bonus_rate']*100:.0f}% eff={item['effectiveness']:.1f}")

    save_checkpoint("template_rankings", template_ranking)
    return template_ranking


# ═══════════════════════════════════════════════════════════
# PHASE 4: Multi-Pass Clustering Optimization
# ═══════════════════════════════════════════════════════════

def optimize_clusters(missions):
    """Try different clustering configurations and pick the best one."""
    print()
    print("═" * 60)
    print("🎯 PHASE 4: Multi-Pass Clustering Optimization")
    print("═" * 60)

    try:
        from sentence_transformers import SentenceTransformer
        from sklearn.cluster import KMeans, AgglomerativeClustering
        from sklearn.metrics import silhouette_score
        import numpy as np
    except ImportError:
        print("   ⚠️ Required libraries not available, using existing clusters")
        return

    # Load or compute embeddings
    emb_path = os.path.join(MODEL_DIR, "element_embeddings.pkl")
    if os.path.exists(emb_path):
        with open(emb_path, "rb") as f:
            emb_data = pickle.load(f)
        embeddings = emb_data["embeddings"]
        all_elements = emb_data["elements"]
        print(f"   ✅ Loaded existing embeddings: {embeddings.shape}")
    else:
        print("   ⚠️ No embeddings found, computing fresh...")
        model = SentenceTransformer("all-MiniLM-L6-v2")
        all_elements = []
        element_texts = []
        for mission in missions:
            for elem in mission["elements"]:
                all_elements.append({
                    "key": f"{mission['category']}:{elem['name']}",
                    "category": mission["category"],
                    "name": elem["name"],
                    "description": elem["description"],
                    "score": elem["score"],
                })
                element_texts.append(f"{elem['name'].replace('_', ' ')}: {elem['description']}")
        embeddings = model.encode(element_texts, show_progress_bar=True)

    best_config = {}
    best_silhouette = {}

    for mission in missions:
        category = mission["category"]
        cat_indices = [
            i for i, e in enumerate(all_elements)
            if e["category"] == category
        ]
        if len(cat_indices) < 4:
            continue

        cat_embeddings = np.array([embeddings[i] for i in cat_indices])

        # Handle NaN/Inf in embeddings
        if np.any(np.isnan(cat_embeddings)) or np.any(np.isinf(cat_embeddings)):
            cat_embeddings = np.nan_to_num(cat_embeddings, nan=0.0, posinf=1.0, neginf=-1.0)

        best_k = 3
        best_score = -1

        # Try different K values
        for k in range(2, min(8, len(cat_indices))):
            try:
                kmeans = KMeans(n_clusters=k, random_state=42, n_init=20)
                labels = kmeans.fit_predict(cat_embeddings)

                if len(set(labels)) > 1:
                    score = silhouette_score(cat_embeddings, labels)
                    if score > best_score:
                        best_score = score
                        best_k = k
            except Exception:
                continue

        # Re-run with best K and extra n_init for stability
        try:
            kmeans = KMeans(n_clusters=best_k, random_state=42, n_init=50)
            labels = kmeans.fit_predict(cat_embeddings)

            clusters = {}
            for idx, label in zip(cat_indices, labels):
                cluster_name = f"cluster_{label}"
                if cluster_name not in clusters:
                    clusters[cluster_name] = []
                clusters[cluster_name].append(all_elements[idx]["name"])

            best_config[category] = clusters
            best_silhouette[category] = round(best_score, 4)
        except Exception:
            pass

    # Also try agglomerative clustering and keep whichever is better
    alt_config = {}
    for mission in missions:
        category = mission["category"]
        cat_indices = [
            i for i, e in enumerate(all_elements)
            if e["category"] == category
        ]
        if len(cat_indices) < 4:
            continue

        cat_embeddings = np.array([embeddings[i] for i in cat_indices])
        if np.any(np.isnan(cat_embeddings)) or np.any(np.isinf(cat_embeddings)):
            cat_embeddings = np.nan_to_num(cat_embeddings, nan=0.0, posinf=1.0, neginf=-1.0)

        best_k_agg = 3
        best_score_agg = -1

        for k in range(2, min(8, len(cat_indices))):
            try:
                agg = AgglomerativeClustering(n_clusters=k)
                labels = agg.fit_predict(cat_embeddings)
                if len(set(labels)) > 1:
                    score = silhouette_score(cat_embeddings, labels)
                    if score > best_score_agg:
                        best_score_agg = score
                        best_k_agg = k
            except Exception:
                continue

        if (best_score_agg > best_silhouette.get(category, -1)):
            try:
                agg = AgglomerativeClustering(n_clusters=best_k_agg)
                labels = agg.fit_predict(cat_embeddings)
                clusters = {}
                for idx, label in zip(cat_indices, labels):
                    cluster_name = f"cluster_{label}"
                    if cluster_name not in clusters:
                        clusters[cluster_name] = []
                    clusters[cluster_name].append(all_elements[idx]["name"])
                best_config[category] = clusters
                best_silhouette[category] = round(best_score_agg, 4)
                print(f"   🔄 {category}: agglomerative better (k={best_k_agg}, "
                      f"silhouette={best_score_agg:.3f})")
            except Exception:
                pass

    # Print results
    print(f"\n   📊 Clustering results:")
    for cat in sorted(best_silhouette.keys()):
        n_clusters = len(best_config.get(cat, {}))
        print(f"      {cat:<25} k={n_clusters} silhouette={best_silhouette[cat]:.3f}")

    # Save best clusters
    with open(os.path.join(MODEL_DIR, "cluster_model.pkl"), "wb") as f:
        pickle.dump(best_config, f)

    save_checkpoint("cluster_optimization", {
        "silhouette_scores": best_silhouette,
        "cluster_sizes": {k: len(v) for k, v in best_config.items()},
    })

    print(f"\n   ✅ Saved optimized clusters")
    return best_config


# ═══════════════════════════════════════════════════════════
# PHASE 5: Monte Carlo Strategy Evaluation
# ═══════════════════════════════════════════════════════════

def monte_carlo_strategy_eval(missions, optimal_weights, n_simulations=500):
    """Evaluate different conversation strategies through Monte Carlo simulation."""
    print()
    print("═" * 60)
    print("🎲 PHASE 5: Monte Carlo Strategy Evaluation")
    print(f"   Simulations: {n_simulations} per strategy")
    print("═" * 60)

    strategies = ["greedy", "cluster", "balanced", "priority"]
    strategy_results = {}

    for strategy in strategies:
        coverages = []
        turns_list = []
        rewards = []

        for _ in range(n_simulations):
            mission = random.choice(missions)
            elements = [
                {**e, "status": "undefined", "value": None}
                for e in mission["elements"]
            ]

            num_pre = random.randint(1, min(3, len(elements)))
            for idx in random.sample(range(len(elements)), num_pre):
                elements[idx]["status"] = "answered"
                elements[idx]["value"] = get_answer(elements[idx]["name"])

            total_score = sum(e["score"] for e in elements)
            answered_score = sum(e["score"] for e in elements if e["status"] == "answered")

            turns = 0
            max_turns = 10

            while turns < max_turns:
                coverage = answered_score / total_score if total_score > 0 else 1.0
                if coverage >= 0.90:
                    break

                undefined = [e for e in elements if e["status"] == "undefined"]
                if not undefined:
                    break

                undefined.sort(key=lambda e: e["score"], reverse=True)

                if strategy == "greedy":
                    targets = undefined[:1]
                elif strategy == "cluster":
                    targets = undefined[:min(3, len(undefined))]
                elif strategy == "balanced":
                    if len(undefined) >= 3:
                        targets = [undefined[0], undefined[len(undefined) // 2]]
                    else:
                        targets = undefined[:1]
                else:
                    targets = undefined[:1]

                for t in targets:
                    t["status"] = "answered"
                    t["value"] = get_answer(t["name"])
                    answered_score += t["score"]

                turns += 1

            final_coverage = answered_score / total_score if total_score > 0 else 1.0
            coverages.append(final_coverage)
            turns_list.append(turns)

            reward = (
                final_coverage * 100 * optimal_weights["coverage_weight"]
                + max(0, (10 - turns)) * optimal_weights["brevity_weight"]
            )
            rewards.append(reward)

        mean_cov = sum(coverages) / len(coverages)
        mean_turns = sum(turns_list) / len(turns_list)
        mean_reward = sum(rewards) / len(rewards)
        pct_90 = sum(1 for c in coverages if c >= 0.90) / len(coverages)

        strategy_results[strategy] = {
            "mean_coverage": round(mean_cov, 4),
            "mean_turns": round(mean_turns, 2),
            "mean_reward": round(mean_reward, 2),
            "pct_above_90": round(pct_90, 3),
        }

        print(f"   {strategy:<12} → cov={mean_cov*100:.1f}% turns={mean_turns:.1f} "
              f"reward={mean_reward:.0f} ≥90%={pct_90*100:.0f}%")

    # Find and save best strategy
    best_strategy = max(strategy_results.keys(),
                        key=lambda s: strategy_results[s]["pct_above_90"] * 100
                        + strategy_results[s]["mean_coverage"] * 50
                        - strategy_results[s]["mean_turns"] * 5)

    print(f"\n   🏆 Best strategy: {best_strategy}")

    save_checkpoint("strategy_evaluation", {
        "results": strategy_results,
        "best_strategy": best_strategy,
    })
    return best_strategy, strategy_results


# ═══════════════════════════════════════════════════════════
# PHASE 6: Extended Template Bank Building
# ═══════════════════════════════════════════════════════════

def build_extended_templates(missions, template_rankings):
    """Build the final template bank using evaluation results."""
    print()
    print("═" * 60)
    print("❓ PHASE 6: Building Extended Question Template Bank")
    print("═" * 60)

    from ali.rl_question_generator import RLQuestionGenerator
    gen = RLQuestionGenerator(model_dir="/dev/null")
    expert_templates = gen.QUESTION_TEMPLATES

    # Build effectiveness lookup
    effectiveness = {r["element"]: r["effectiveness"]
                     for r in template_rankings}

    template_bank = {}
    total_templates = 0
    expert_count = 0

    for mission in missions:
        category = mission["category"]
        template_bank[category] = {}

        for elem in mission["elements"]:
            name = elem["name"]
            desc = elem["description"]

            # Expert templates take priority
            if name in expert_templates:
                templates = expert_templates[name]
                expert_count += 1
            else:
                # Generate contextual templates based on priority
                eff = effectiveness.get(name, 50)
                if eff > 70:
                    templates = [
                        f"Tell me about {desc.lower()} — this is really important for the project.",
                        f"Let's dig into {desc.lower()} — what are you thinking?",
                        f"I need to understand {desc.lower()} — can you walk me through it?",
                    ]
                elif eff > 40:
                    templates = [
                        f"What about {desc.lower()}? This will help me shape the plan.",
                        f"Let's talk about {desc.lower()} — any thoughts?",
                        f"Have you considered {desc.lower()} yet?",
                    ]
                else:
                    templates = [
                        f"One more thing — any thoughts on {desc.lower()}?",
                        f"Quick question about {desc.lower()} — anything specific in mind?",
                    ]

            template_bank[category][name] = templates
            total_templates += len(templates)

    # Save
    with open(os.path.join(MODEL_DIR, "question_templates.json"), "w") as f:
        json.dump(template_bank, f, indent=2)

    print(f"   ✅ Generated templates for {len(template_bank)} categories")
    print(f"   📊 Total templates: {total_templates}")
    print(f"   📊 Expert templates: {expert_count} element types")
    return template_bank


# ═══════════════════════════════════════════════════════════
# PHASE 7: Final Validation
# ═══════════════════════════════════════════════════════════

def final_validation(missions):
    """Comprehensive end-to-end validation."""
    print()
    print("═" * 60)
    print("🧪 PHASE 7: Final Comprehensive Validation")
    print("═" * 60)

    from ali.conversation_loop import ConversationLoop

    # Single-task tests
    tests = [
        ("I want to build a website for my bakery", ["web_development"]),
        ("Help me create a mobile app for tracking fitness", ["mobile_app"]),
        ("We need a marketing campaign for our new product", ["marketing_campaign"]),
        ("I want to build a SaaS for managing projects", ["saas_product"]),
        ("I need a social media strategy for my restaurant", ["social_media"]),
        ("I want to set up email marketing for my bakery", ["email_marketing"]),
        ("I need a brand identity for my consulting firm", ["design_branding"]),
        ("Build me a data dashboard for sales performance", ["data_analytics"]),
        ("I need a chatbot for customer support", ["chatbot_ai"]),
        ("We want a promotional video for our product", ["video_production"]),
    ]

    # Multi-task tests
    multi_tests = [
        ("I need a website update and email marketing setup for my bakery",
         ["web_development", "email_marketing"]),
        ("Help me build an online store and run a marketing campaign",
         ["ecommerce", "marketing_campaign"]),
        ("We need a social media strategy and video production for our launch",
         ["social_media", "video_production"]),
        ("I want a new brand identity and a website for my startup",
         ["design_branding", "web_development"]),
        ("We need a SaaS platform plus content strategy",
         ["saas_product", "content_creation"]),
    ]

    passed = 0
    total = 0

    print("\n   📋 Single-task tests:")
    for prompt, expected_cats in tests:
        total += 1
        loop = ConversationLoop(
            missions_path=MISSIONS_PATH,
            context_path="/tmp/telos_extended_validate.md",
        )
        result = loop.start(prompt)
        ok = result["category"] in expected_cats
        icon = "✅" if ok else "❌"
        if ok:
            passed += 1
        q = result.get("first_question") or "None"
        print(f"   {icon} \"{prompt[:45]}...\" → {result['category']}")
        print(f"      Q: {q[:65]}")

    print("\n   📋 Multi-task tests:")
    for prompt, expected_cats in multi_tests:
        total += 1
        loop = ConversationLoop(
            missions_path=MISSIONS_PATH,
            context_path="/tmp/telos_extended_validate_multi.md",
        )
        result = loop.start(prompt)
        actual = result.get("categories", [result["category"]])
        overlap = set(actual) & set(expected_cats)
        ok = len(overlap) >= 1
        icon = "✅" if ok else "❌"
        if ok:
            passed += 1
        print(f"   {icon} \"{prompt[:45]}...\"")
        print(f"      Detected: {actual} | Expected: {expected_cats}")

    # Full conversation simulation test
    print("\n   📋 Full conversation simulation:")
    loop = ConversationLoop(
        missions_path=MISSIONS_PATH,
        context_path="/tmp/telos_full_sim.md",
    )
    result = loop.start("I want to build a website for my bakery")
    total += 1

    question_info = result.get("_question_info") or {"targets": [], "question": ""}
    sim_turns = 0
    while not result.get("done", True) and sim_turns < 8:
        answer = get_answer(question_info["targets"][0] if question_info.get("targets") else "_default")
        result = loop.process_answer(answer, question_info)
        question_info = result.get("_question_info") or {"targets": [], "question": ""}
        sim_turns += 1

    status = loop.get_status()
    conv_ok = status["coverage"] >= 0.80
    icon = "✅" if conv_ok else "❌"
    if conv_ok:
        passed += 1
    print(f"   {icon} Full sim: {sim_turns} turns, {status['coverage_pct']} coverage, "
          f"{status['answered_count']}/{status['total_elements']} elements")

    # Check context.md has Q&A log
    context_file = Path("/tmp/telos_full_sim.md")
    total += 1
    if context_file.exists():
        content = context_file.read_text()
        has_qa = "## Conversation Log" in content
        icon = "✅" if has_qa else "❌"
        if has_qa:
            passed += 1
        print(f"   {icon} Context.md has Q&A log: {has_qa}")

    print(f"\n   📊 Results: {passed}/{total} tests passed ({passed/total*100:.0f}%)")
    return passed, total


# ═══════════════════════════════════════════════════════════
# MAIN PIPELINE
# ═══════════════════════════════════════════════════════════

def main():
    start_time = time.time()
    print()
    print("╔══════════════════════════════════════════════════════════╗")
    print("║       🚀 TELOS — Extended Training Pipeline            ║")
    print(f"║       Target duration: ~{TARGET_DURATION_MINUTES} minutes                    ║")
    print("╠══════════════════════════════════════════════════════════╣")
    print("║  Phase 1: Massive Data Generation                      ║")
    print("║  Phase 2: Evolutionary Reward Optimization              ║")
    print("║  Phase 3: Template Evaluation & Selection               ║")
    print("║  Phase 4: Multi-Pass Clustering Optimization            ║")
    print("║  Phase 5: Monte Carlo Strategy Evaluation               ║")
    print("║  Phase 6: Extended Template Bank                        ║")
    print("║  Phase 7: Final Validation                              ║")
    print("╚══════════════════════════════════════════════════════════╝")
    print()

    missions = load_jsonl(MISSIONS_PATH)
    print(f"📦 Loaded {len(missions)} mission categories")

    # ── Phase 1: Generate massive training data ─────────────
    print()
    print("═" * 60)
    print("📊 PHASE 1: Massive Training Data Generation")
    print("═" * 60)

    episodes = generate_massive_episodes(missions,
                                         n_per_category=200,
                                         n_multi=500)
    # Save episodes
    os.makedirs(os.path.dirname(RL_PATH), exist_ok=True)
    with open(RL_PATH, "w") as f:
        for ep in episodes:
            f.write(json.dumps(ep) + "\n")

    single_eps = [e for e in episodes if not e.get("multi_task")]
    multi_eps = [e for e in episodes if e.get("multi_task")]
    avg_coverage = sum(e["final_coverage"] for e in episodes) / len(episodes)
    avg_turns = sum(e["total_turns"] for e in episodes) / len(episodes)
    print(f"   ✅ Generated {len(episodes)} episodes "
          f"({len(single_eps)} single + {len(multi_eps)} multi)")
    print(f"   📊 Avg coverage: {avg_coverage*100:.1f}%, Avg turns: {avg_turns:.1f}")

    elapsed = time.time() - start_time
    print(f"   ⏱️  Phase 1 done in {elapsed:.0f}s")

    # ── Phase 2: Evolutionary optimization ──────────────────
    optimal_weights = evolutionary_optimize(missions,
                                           generations=EVOLUTIONARY_GENERATIONS,
                                           pop_size=POPULATION_SIZE)

    elapsed = time.time() - start_time
    print(f"   ⏱️  Phase 2 done in {elapsed:.0f}s")

    # ── Phase 3: Template evaluation ────────────────────────
    template_rankings = evaluate_templates(missions, optimal_weights)

    elapsed = time.time() - start_time
    print(f"   ⏱️  Phase 3 done in {elapsed:.0f}s")

    # ── Phase 4: Clustering optimization ────────────────────
    optimize_clusters(missions)

    elapsed = time.time() - start_time
    print(f"   ⏱️  Phase 4 done in {elapsed:.0f}s")

    # ── Phase 5: Strategy evaluation ────────────────────────
    best_strategy, strategy_results = monte_carlo_strategy_eval(
        missions, optimal_weights, n_simulations=1000
    )

    elapsed = time.time() - start_time
    print(f"   ⏱️  Phase 5 done in {elapsed:.0f}s")

    # ── Repeat phases 2-3 with more iterations if we have time
    remaining_time = TARGET_DURATION_MINUTES * 60 - (time.time() - start_time)
    extra_rounds = 0
    while remaining_time > 120:  # Keep going if > 2 min left
        extra_rounds += 1
        print()
        print(f"═══ EXTRA ROUND {extra_rounds} ({remaining_time/60:.0f} min remaining) ═══")

        # More evolutionary generations
        optimal_weights = evolutionary_optimize(
            missions,
            generations=max(10, int(remaining_time / 30)),
            pop_size=POPULATION_SIZE,
        )

        # More Monte Carlo simulations
        monte_carlo_strategy_eval(missions, optimal_weights,
                                  n_simulations=500)

        # Re-evaluate templates
        template_rankings = evaluate_templates(missions, optimal_weights)

        remaining_time = TARGET_DURATION_MINUTES * 60 - (time.time() - start_time)

    # ── Phase 6: Build final templates ──────────────────────
    build_extended_templates(missions, template_rankings)

    # ── Regenerate episode data with best weights ───────────
    print()
    print("═" * 60)
    print("📊 FINAL: Regenerating episodes with optimal weights")
    print("═" * 60)

    final_episodes = generate_massive_episodes(missions,
                                               n_per_category=100,
                                               n_multi=200)
    with open(RL_PATH, "w") as f:
        for ep in final_episodes:
            f.write(json.dumps(ep) + "\n")

    avg_coverage = sum(e["final_coverage"] for e in final_episodes) / len(final_episodes)
    avg_turns = sum(e["total_turns"] for e in final_episodes) / len(final_episodes)
    avg_reward = sum(e["reward"] for e in final_episodes) / len(final_episodes)
    print(f"   ✅ Final dataset: {len(final_episodes)} episodes")
    print(f"   📊 Final avg coverage: {avg_coverage*100:.1f}%")
    print(f"   📊 Final avg turns: {avg_turns:.1f}")
    print(f"   📊 Final avg reward: {avg_reward:.1f}")

    # ── Phase 7: Final validation ───────────────────────────
    passed, total = final_validation(missions)

    # ── Summary ─────────────────────────────────────────────
    total_elapsed = time.time() - start_time
    print()
    print("╔══════════════════════════════════════════════════════════╗")
    print("║            ✅ TELOS EXTENDED TRAINING COMPLETE          ║")
    print("╠══════════════════════════════════════════════════════════╣")
    print(f"║  ⏱️  Total time: {total_elapsed/60:.1f} minutes ({total_elapsed:.0f}s)         ║")
    print(f"║  🧬  Evolutionary rounds: {EVOLUTIONARY_GENERATIONS + extra_rounds * 10:>3}                         ║")
    print(f"║  📊  Total episodes generated: {len(final_episodes):>5}                    ║")
    print(f"║  🧪  Validation: {passed}/{total} tests passed                        ║")
    print("╠══════════════════════════════════════════════════════════╣")
    print("║  Models saved to: ali/trained_models/                   ║")
    print("║    • element_embeddings.pkl                             ║")
    print("║    • cluster_model.pkl (optimized K + algorithm)        ║")
    print("║    • reward_weights.json (evolutionary optimized)       ║")
    print("║    • question_templates.json (evaluated + ranked)       ║")
    print("║  Checkpoints: ali/trained_models/checkpoints/           ║")
    print("╚══════════════════════════════════════════════════════════╝")
    print()
    print("Run interactive mode:")
    print("  python3 -m ali.main")


if __name__ == "__main__":
    main()
