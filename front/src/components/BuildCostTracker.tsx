"use client";

import type { CostEstimateData } from "./ChatContext";

interface BuildCostTrackerProps {
    estimate: CostEstimateData;
    currentIteration: number;
    phase: "building" | "done";
    prdCount?: number;
}

function formatUsd(amount: number): string {
    return amount < 0.01 ? "<$0.01" : `$${amount.toFixed(2)}`;
}

/**
 * Compute a running cost estimate based on completed iterations.
 * Uses the accepted estimate's breakdown to derive per-iteration cost.
 */
function computeRunningCost(estimate: CostEstimateData, iteration: number): number {
    // Fixed costs: plan + PRD generation
    const planPhase = estimate.breakdown.find((p) => p.phase === "plan_generation");
    const prdPhase = estimate.breakdown.find((p) => p.phase === "prd_generation");
    const fixedCost = (planPhase?.cost_usd ?? 0) + (prdPhase?.cost_usd ?? 0);

    // Ralph loop: find the ralph phase and compute per-iteration cost
    const ralphPhase = estimate.breakdown.find((p) => p.phase.startsWith("ralph_loop_"));
    if (!ralphPhase) return fixedCost;

    // Extract iteration count from phase name (e.g. "ralph_loop_6_iterations")
    const match = ralphPhase.phase.match(/ralph_loop_(\d+)_iterations/);
    const typicalIters = match ? parseInt(match[1], 10) : 1;
    const perIterCost = ralphPhase.cost_usd / typicalIters;

    return fixedCost + perIterCost * iteration;
}

export default function BuildCostTracker({ estimate, currentIteration, phase, prdCount }: BuildCostTrackerProps) {
    const maxIters = estimate.max_iterations;
    const progress = Math.min(currentIteration / maxIters, 1);
    const runningCost = computeRunningCost(estimate, currentIteration);
    const isDone = phase === "done";

    return (
        <div className="bct">
            {/* Progress bar */}
            <div className="bct__progress-track">
                <div
                    className={`bct__progress-fill ${isDone ? "bct__progress-fill--done" : ""}`}
                    style={{ width: `${progress * 100}%` }}
                />
            </div>

            <div className="bct__stats">
                <div className="bct__stat">
                    <span className="bct__stat-label">Iteration</span>
                    <span className="bct__stat-value">{currentIteration} / {maxIters}</span>
                </div>
                <div className="bct__stat">
                    <span className="bct__stat-label">{isDone ? "Final" : "Running"}</span>
                    <span className="bct__stat-value bct__stat-value--cost">{formatUsd(runningCost)}</span>
                </div>
                <div className="bct__stat">
                    <span className="bct__stat-label">Estimate</span>
                    <span className="bct__stat-value bct__stat-value--muted">
                        {formatUsd(estimate.low_usd)} – {formatUsd(estimate.high_usd)}
                    </span>
                </div>
                <div className="bct__stat">
                    <span className="bct__stat-label">PRDs</span>
                    <span className="bct__stat-value bct__stat-value--muted">
                        {prdCount != null ? prdCount : `~${estimate.estimated_prd_count}`}
                    </span>
                </div>
                <div className="bct__stat">
                    <span className="bct__stat-label">Model</span>
                    <span className="bct__stat-value bct__stat-value--muted">{estimate.model}</span>
                </div>
            </div>
        </div>
    );
}
