"use client";

import type { PrdProgressData } from "./ChatContext";

interface Props {
    progress: PrdProgressData;
}

export default function PrdProgressPanel({ progress }: Props) {
    if (progress.prds.length === 0) return null;

    return (
        <div className="prd-panel">
            {/* Overall progress */}
            <div className="prd-panel__header">
                <span className="prd-panel__label">PRD Progress</span>
                <span className="prd-panel__summary">
                    {progress.total_done}/{progress.total_items} ({progress.overall_percent}%)
                </span>
            </div>
            <div className="prd-panel__bar-track">
                <div
                    className={`prd-panel__bar-fill ${progress.overall_percent >= 100 ? "prd-panel__bar-fill--done" : ""}`}
                    style={{ width: `${Math.min(progress.overall_percent, 100)}%` }}
                />
            </div>

            {/* Per-PRD rows */}
            <div className="prd-panel__list">
                {progress.prds.map((prd) => (
                    <div
                        key={prd.filename}
                        className={`prd-item ${prd.total > 0 && prd.done === prd.total ? "prd-item--done" : ""}`}
                    >
                        <span className="prd-item__check">
                            {prd.total > 0 && prd.done === prd.total ? "\u2713" : ""}
                        </span>
                        <span className="prd-item__title">{prd.title}</span>
                        <div className="prd-item__bar-track">
                            <div
                                className={`prd-item__bar-fill ${prd.total > 0 && prd.done === prd.total ? "prd-item__bar-fill--done" : ""}`}
                                style={{ width: `${prd.total > 0 ? Math.min(prd.percent, 100) : 0}%` }}
                            />
                        </div>
                        <span className="prd-item__count">
                            {prd.done}/{prd.total}
                        </span>
                    </div>
                ))}
            </div>
        </div>
    );
}
