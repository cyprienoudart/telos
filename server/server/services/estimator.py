"""Heuristic cost estimator for Telos builds.

Estimates API credit usage based on transcript size, project complexity,
model choice, and iteration count. Returns a low–high range since actual
usage depends on code review outcomes (early approvals vs max iterations).

Pricing source: https://platform.claude.com/docs/en/about-claude/pricing
All estimates include a 50% profit margin.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field


# Anthropic API pricing per 1M tokens (USD) — Claude 4.5/4.6 models
MODEL_PRICING: dict[str, dict[str, float]] = {
    "opus":   {"input": 5.0,  "output": 25.0},
    "sonnet": {"input": 3.0,  "output": 15.0},
    "haiku":  {"input": 1.0,  "output": 5.0},
}

# Less capable models need more iterations before reviewer approval.
# Values are (P30, P50, P90) expressed as fractions of max_iterations.
_ITERATION_PERCENTILES: dict[str, tuple[float, float, float]] = {
    "opus":   (0.30, 0.45, 0.70),
    "sonnet": (0.45, 0.60, 0.85),
    "haiku":  (0.60, 0.75, 0.95),
}

PROFIT_MARGIN = 1.50  # 50% margin


@dataclass
class PhaseEstimate:
    """Cost estimate for a single build phase."""

    phase: str
    input_tokens: int
    output_tokens: int
    model: str
    cost_usd: float


@dataclass
class CostEstimate:
    """Aggregated cost estimate with low/typical/high range."""

    low_usd: float
    typical_usd: float
    high_usd: float
    model: str
    max_iterations: int
    estimated_prd_count: int
    breakdown: list[PhaseEstimate] = field(default_factory=list)


def _token_cost(input_tokens: int, output_tokens: int, model: str) -> float:
    """Compute USD cost for a given token count and model."""
    pricing = MODEL_PRICING.get(model, MODEL_PRICING["sonnet"])
    return (
        input_tokens / 1_000_000 * pricing["input"]
        + output_tokens / 1_000_000 * pricing["output"]
    )


def estimate_build_cost(
    transcript_len: int,
    total_elements: int,
    max_iterations: int = 10,
    model: str = "opus",
    prd_count: int | None = None,
) -> CostEstimate:
    """Estimate build cost based on project parameters.

    Args:
        transcript_len: Length of the interview transcript in characters.
        total_elements: Number of Ali elements (proxy for complexity).
        max_iterations: Maximum Ralph loop iterations configured.
        model: Model used for the Ralph loop (plan/PRD use the same model).
        prd_count: If provided, use this instead of heuristic estimate.
            Pass the actual count from disk after PRD generation.

    Returns:
        CostEstimate with low/typical/high USD range and per-phase breakdown.
        All values include a 50% profit margin.
    """
    transcript_tokens = transcript_len // 4

    # Use actual PRD count if provided, otherwise estimate from element count
    estimated_prd_count = prd_count if prd_count is not None else max(1, math.ceil(total_elements / 10))

    # ── Plan generation ──────────────────────────────────────────────
    plan_input = transcript_tokens + 2000  # transcript + template/prompt
    plan_output = 2000
    plan_cost = _token_cost(plan_input, plan_output, model)

    plan_phase = PhaseEstimate(
        phase="plan_generation",
        input_tokens=plan_input,
        output_tokens=plan_output,
        model=model,
        cost_usd=round(plan_cost * PROFIT_MARGIN, 4),
    )

    # ── PRD generation ───────────────────────────────────────────────
    prd_input = plan_output + 3000  # plan + template
    prd_output = 2000 * estimated_prd_count
    prd_cost = _token_cost(prd_input, prd_output, model)

    prd_phase = PhaseEstimate(
        phase="prd_generation",
        input_tokens=prd_input,
        output_tokens=prd_output,
        model=model,
        cost_usd=round(prd_cost * PROFIT_MARGIN, 4),
    )

    # ── Ralph iterations (user's chosen model) ───────────────────────
    # Each iteration: base context (PRDs + progress + prompt) + growth per iter
    base_input_per_iter = 8000 + (1000 * estimated_prd_count)
    growth_per_iter = 2000  # accumulated progress, diffs, etc.
    output_per_iter = 3000

    def ralph_cost_for_n(n: int) -> tuple[float, PhaseEstimate]:
        total = 0.0
        for i in range(n):
            iter_input = base_input_per_iter + growth_per_iter * i
            total += _token_cost(iter_input, output_per_iter, model)
        total_input = sum(
            base_input_per_iter + growth_per_iter * i for i in range(n)
        )
        total_output = output_per_iter * n
        phase = PhaseEstimate(
            phase=f"ralph_loop_{n}_iterations",
            input_tokens=total_input,
            output_tokens=total_output,
            model=model,
            cost_usd=round(total * PROFIT_MARGIN, 4),
        )
        return total, phase

    fixed_cost = plan_cost + prd_cost

    # Model-dependent iteration percentiles
    p30, p50, p90 = _ITERATION_PERCENTILES.get(model, (0.45, 0.60, 0.85))

    low_iters = max(1, math.ceil(max_iterations * p30))
    typical_iters = max(1, math.ceil(max_iterations * p50))
    high_iters = max(1, math.ceil(max_iterations * p90))

    low_ralph, _ = ralph_cost_for_n(low_iters)
    low_usd = (fixed_cost + low_ralph) * PROFIT_MARGIN

    typical_ralph, typical_phase = ralph_cost_for_n(typical_iters)
    typical_usd = (fixed_cost + typical_ralph) * PROFIT_MARGIN

    high_ralph, _ = ralph_cost_for_n(high_iters)
    high_usd = (fixed_cost + high_ralph) * PROFIT_MARGIN

    # Build breakdown using typical scenario
    breakdown = [plan_phase, prd_phase, typical_phase]

    return CostEstimate(
        low_usd=round(low_usd, 2),
        typical_usd=round(typical_usd, 2),
        high_usd=round(high_usd, 2),
        model=model,
        max_iterations=max_iterations,
        estimated_prd_count=estimated_prd_count,
        breakdown=breakdown,
    )
