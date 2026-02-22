"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import type { TrajectoryEvent } from "./ChatContext";

// ── Tool pill color categories ──────────────────────────────────────────

const TOOL_COLORS: Record<string, string> = {
    Read: "#60a5fa",
    Glob: "#60a5fa",
    Grep: "#60a5fa",
    Write: "#34d399",
    Edit: "#34d399",
    NotebookEdit: "#34d399",
    Bash: "#fbbf24",
    Task: "#a78bfa",
    WebFetch: "#22d3ee",
    WebSearch: "#22d3ee",
};

function getToolColor(name: string): string {
    if (TOOL_COLORS[name]) return TOOL_COLORS[name];
    if (name.startsWith("mcp__")) return "#22d3ee";
    return "#94a3b8"; // default slate
}

function getToolLabel(name: string): string {
    // Shorten MCP tool names: mcp__gemini-context__summarize → gemini-context.summarize
    if (name.startsWith("mcp__")) {
        return name.slice(5).replace(/__/g, ".");
    }
    return name;
}

function extractFilePath(input: Record<string, unknown>): string | null {
    for (const key of ["file_path", "path", "command", "pattern", "url"]) {
        if (typeof input[key] === "string") {
            const val = input[key] as string;
            return val.length > 80 ? val.slice(0, 77) + "..." : val;
        }
    }
    return null;
}

// ── Sub-components ──────────────────────────────────────────────────────

function PhaseIndicator({ label, message }: { label: string; message: string }) {
    return (
        <div className="bs-phase">
            <div className="bs-spinner" />
            <div>
                <span className="bs-phase-label">{label}</span>
                <span className="bs-phase-message">{message}</span>
            </div>
        </div>
    );
}

function IterationHeader({ iteration, model }: { iteration: number; model?: string }) {
    return (
        <div className="bs-iteration-header">
            <span className="bs-iteration-badge">Iteration {iteration}</span>
            {model && <span className="bs-iteration-model">{model}</span>}
        </div>
    );
}

function IterationFooter({ status, reason }: { status: string; reason?: string }) {
    const statusClass =
        status === "approved" ? "bs-status--approved" :
        status === "denied" ? "bs-status--denied" :
        "bs-status--neutral";

    return (
        <div className={`bs-iteration-footer ${statusClass}`}>
            <span className="bs-status-dot" />
            <span>{status}</span>
            {reason && <span className="bs-status-reason"> — {reason}</span>}
        </div>
    );
}

function TextBlock({ text }: { text: string }) {
    if (!text.trim()) return null;
    return <div className="bs-text">{text}</div>;
}

function ToolPill({
    name,
    input,
    result,
}: {
    name: string;
    input?: Record<string, unknown>;
    result?: string;
}) {
    const [expanded, setExpanded] = useState(false);
    const color = getToolColor(name);
    const label = getToolLabel(name);
    const filePath = input ? extractFilePath(input) : null;

    return (
        <div className="bs-tool-pill-wrapper">
            <button
                className="bs-tool-pill"
                style={{ borderColor: color, color }}
                onClick={() => setExpanded(!expanded)}
                type="button"
            >
                <span className="bs-tool-dot" style={{ background: color }} />
                <span className="bs-tool-name">{label}</span>
                {filePath && <span className="bs-tool-path">{filePath}</span>}
                <span className={`bs-tool-chevron ${expanded ? "bs-tool-chevron--open" : ""}`}>
                    &#9662;
                </span>
            </button>
            {expanded && (
                <div className="bs-tool-detail">
                    {input && Object.keys(input).length > 0 && (
                        <div className="bs-tool-section">
                            <div className="bs-tool-section-label">Input</div>
                            <pre className="bs-tool-pre">{JSON.stringify(input, null, 2)}</pre>
                        </div>
                    )}
                    {result && (
                        <div className="bs-tool-section">
                            <div className="bs-tool-section-label">Result</div>
                            <pre className="bs-tool-pre">
                                {result.length > 2000 ? result.slice(0, 2000) + "\n... (truncated)" : result}
                            </pre>
                        </div>
                    )}
                </div>
            )}
        </div>
    );
}

// ── Main component ──────────────────────────────────────────────────────

interface BuildStreamProps {
    trajectory: TrajectoryEvent[];
    phase: "building" | "done";
}

interface ParsedBlock {
    key: string;
    type: "text" | "tool" | "iteration_header" | "iteration_footer" | "phase";
    text?: string;
    toolName?: string;
    toolInput?: Record<string, unknown>;
    toolResult?: string;
    toolId?: string;
    iteration?: number;
    model?: string;
    status?: string;
    reason?: string;
    phaseLabel?: string;
    phaseMessage?: string;
}

export default function BuildStream({ trajectory, phase }: BuildStreamProps) {
    const containerRef = useRef<HTMLDivElement>(null);
    const [autoScroll, setAutoScroll] = useState(true);

    // Parse trajectory events into renderable blocks
    const blocks = parseTrajectory(trajectory);

    // Auto-scroll when new content arrives
    useEffect(() => {
        if (autoScroll && containerRef.current) {
            containerRef.current.scrollTop = containerRef.current.scrollHeight;
        }
    }, [blocks.length, autoScroll]);

    // Scroll-lock detection
    const handleScroll = useCallback(() => {
        const el = containerRef.current;
        if (!el) return;
        const atBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 40;
        setAutoScroll(atBottom);
    }, []);

    if (blocks.length === 0 && phase === "building") {
        return (
            <div className="bs-container">
                <div className="bs-empty">
                    <div className="bs-spinner" />
                    <span>Preparing build...</span>
                </div>
            </div>
        );
    }

    return (
        <div className="bs-container">
            <div className="bs-header">
                <span className="bs-header-title">Build Log</span>
                {phase === "building" && <span className="bs-live-dot" />}
                {!autoScroll && (
                    <button
                        className="bs-scroll-btn"
                        onClick={() => {
                            setAutoScroll(true);
                            containerRef.current?.scrollTo({
                                top: containerRef.current.scrollHeight,
                                behavior: "smooth",
                            });
                        }}
                        type="button"
                    >
                        ↓ Follow
                    </button>
                )}
            </div>
            <div className="bs-log" ref={containerRef} onScroll={handleScroll}>
                {blocks.map((block) => {
                    switch (block.type) {
                        case "phase":
                            return (
                                <PhaseIndicator
                                    key={block.key}
                                    label={block.phaseLabel!}
                                    message={block.phaseMessage!}
                                />
                            );
                        case "iteration_header":
                            return (
                                <IterationHeader
                                    key={block.key}
                                    iteration={block.iteration!}
                                    model={block.model}
                                />
                            );
                        case "iteration_footer":
                            return (
                                <IterationFooter
                                    key={block.key}
                                    status={block.status!}
                                    reason={block.reason}
                                />
                            );
                        case "text":
                            return <TextBlock key={block.key} text={block.text!} />;
                        case "tool":
                            return (
                                <ToolPill
                                    key={block.key}
                                    name={block.toolName!}
                                    input={block.toolInput}
                                    result={block.toolResult}
                                />
                            );
                        default:
                            return null;
                    }
                })}
            </div>
        </div>
    );
}

// ── Parse trajectory events into blocks ─────────────────────────────────

function parseTrajectory(events: TrajectoryEvent[]): ParsedBlock[] {
    const blocks: ParsedBlock[] = [];
    // Map tool_use IDs to their block index for attaching results
    const toolBlockMap = new Map<string, number>();

    for (let i = 0; i < events.length; i++) {
        const evt = events[i];
        const evtType = evt.type as string;

        if (evtType === "phase") {
            blocks.push({
                key: `phase-${i}`,
                type: "phase",
                phaseLabel: (evt.phase as string) ?? "working",
                phaseMessage: (evt.message as string) ?? "",
            });
        } else if (evtType === "iteration_start") {
            blocks.push({
                key: `iter-start-${i}`,
                type: "iteration_header",
                iteration: evt.iteration as number,
                model: evt.model as string | undefined,
            });
        } else if (evtType === "iteration_end") {
            blocks.push({
                key: `iter-end-${i}`,
                type: "iteration_footer",
                status: evt.status as string,
                reason: evt.reason as string | undefined,
            });
        } else if (evtType === "assistant") {
            // Extract text blocks and tool_use blocks from assistant message
            const message = evt.message as { content?: Array<Record<string, unknown>> } | undefined;
            const content = message?.content;
            if (Array.isArray(content)) {
                for (let j = 0; j < content.length; j++) {
                    const block = content[j];
                    if (block.type === "text" && typeof block.text === "string") {
                        blocks.push({
                            key: `text-${i}-${j}`,
                            type: "text",
                            text: block.text,
                        });
                    } else if (block.type === "tool_use") {
                        const blockIdx = blocks.length;
                        const toolId = block.id as string;
                        blocks.push({
                            key: `tool-${i}-${j}`,
                            type: "tool",
                            toolName: block.name as string,
                            toolInput: block.input as Record<string, unknown> | undefined,
                            toolId,
                        });
                        if (toolId) {
                            toolBlockMap.set(toolId, blockIdx);
                        }
                    }
                }
            }
        } else if (evtType === "tool_result") {
            // Attach result to its matching tool_use block
            const toolUseId = evt.tool_use_id as string | undefined;
            const content = evt.content as string | undefined;
            if (toolUseId && toolBlockMap.has(toolUseId)) {
                const idx = toolBlockMap.get(toolUseId)!;
                blocks[idx] = { ...blocks[idx], toolResult: content };
            }
        } else if (evtType === "result") {
            // Final result text from Claude
            const resultText = evt.result as string | undefined;
            if (resultText) {
                blocks.push({
                    key: `result-${i}`,
                    type: "text",
                    text: resultText,
                });
            }
        }
    }

    return blocks;
}
