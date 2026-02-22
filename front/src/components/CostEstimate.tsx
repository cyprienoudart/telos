"use client";

import type { CostEstimateData } from "./ChatContext";

const MODELS = [
    { id: "opus", label: "Opus", description: "Most capable" },
    { id: "sonnet", label: "Sonnet", description: "Balanced" },
    { id: "haiku", label: "Haiku", description: "Fastest" },
] as const;

interface CostEstimateProps {
    estimate: CostEstimateData;
    loading?: boolean;
    onModelChange: (model: string) => void;
    onConfirm: () => void;
    onDecline: () => void;
}

function formatUsd(amount: number): string {
    return amount < 0.01 ? "<$0.01" : `$${amount.toFixed(2)}`;
}

function phaseName(phase: string): string {
    if (phase === "plan_generation") return "Plan generation";
    if (phase === "prd_generation") return "PRD generation";
    if (phase.startsWith("ralph_loop_")) {
        const n = phase.replace("ralph_loop_", "").replace("_iterations", "");
        return `Build loop (~${n} iterations)`;
    }
    return phase;
}

export default function CostEstimate({ estimate, loading, onModelChange, onConfirm, onDecline }: CostEstimateProps) {
    return (
        <div className={`cost-estimate ${loading ? "cost-estimate--loading" : ""}`}>
            <div className="cost-estimate__header">
                <span className="cost-estimate__title">Estimated Build Cost</span>
                <span className="cost-estimate__subtitle">
                    Up to {estimate.max_iterations} iterations &middot; ~{estimate.estimated_prd_count} PRD{estimate.estimated_prd_count !== 1 ? "s" : ""} (estimated)
                </span>
            </div>

            {/* Model selector */}
            <div className="cost-estimate__model-selector">
                {MODELS.map((m) => (
                    <button
                        key={m.id}
                        type="button"
                        className={`cost-estimate__model-btn ${estimate.model === m.id ? "cost-estimate__model-btn--active" : ""}`}
                        onClick={() => onModelChange(m.id)}
                        disabled={loading}
                    >
                        <span className="cost-estimate__model-label">{m.label}</span>
                        <span className="cost-estimate__model-desc">{m.description}</span>
                    </button>
                ))}
            </div>

            <div className="cost-estimate__range">
                <div className="cost-estimate__range-item cost-estimate__range-item--low">
                    <span className="cost-estimate__range-label">Low</span>
                    <span className="cost-estimate__range-value">{formatUsd(estimate.low_usd)}</span>
                </div>
                <div className="cost-estimate__range-item cost-estimate__range-item--typical">
                    <span className="cost-estimate__range-label">Typical</span>
                    <span className="cost-estimate__range-value">{formatUsd(estimate.typical_usd)}</span>
                </div>
                <div className="cost-estimate__range-item cost-estimate__range-item--high">
                    <span className="cost-estimate__range-label">High</span>
                    <span className="cost-estimate__range-value">{formatUsd(estimate.high_usd)}</span>
                </div>
            </div>

            <div className="cost-estimate__breakdown">
                <span className="cost-estimate__breakdown-title">Breakdown (typical)</span>
                {estimate.breakdown.map((phase, i) => (
                    <div key={i} className="cost-estimate__phase">
                        <span className="cost-estimate__phase-name">{phaseName(phase.phase)}</span>
                        <span className="cost-estimate__phase-model">{phase.model}</span>
                        <span className="cost-estimate__phase-cost">{formatUsd(phase.cost_usd)}</span>
                    </div>
                ))}
            </div>

            <div className="cost-estimate__actions">
                <button
                    className="cost-estimate__btn cost-estimate__btn--confirm"
                    onClick={onConfirm}
                    disabled={loading}
                    type="button"
                >
                    Start Build
                </button>
                <button
                    className="cost-estimate__btn cost-estimate__btn--cancel"
                    onClick={onDecline}
                    disabled={loading}
                    type="button"
                >
                    Cancel
                </button>
            </div>
        </div>
    );
}
