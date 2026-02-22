"use client";

import { useEffect, useRef, useState, useCallback } from "react";
import { useChatContext } from "./ChatContext";
import BuildCostTracker from "./BuildCostTracker";
import PrdProgressPanel from "./PrdProgressPanel";
import ChatInputBar from "./ChatInputBar";
import CostEstimate from "./CostEstimate";
import VoiceOrb from "./VoiceOrb";
import { useVoiceEngine } from "@/hooks/useVoiceEngine";

function BuildProgressBar({ phase, prdProgress }: {
    phase: "planning" | "building";
    prdProgress: { overall_percent: number } | null;
}) {
    const isPlanning = phase === "planning";
    const percent = isPlanning ? null : (prdProgress?.overall_percent ?? 0);
    const label = isPlanning
        ? "Generating plan & PRDs\u2026"
        : `Building\u2026 ${Math.round(percent ?? 0)}%`;

    return (
        <div className="build-progress-bar">
            <div className="build-progress-bar__label">{label}</div>
            <div className="build-progress-bar__track">
                <div
                    className={`build-progress-bar__fill ${isPlanning ? "build-progress-bar__fill--indeterminate" : ""}`}
                    style={isPlanning ? undefined : { width: `${percent}%` }}
                />
            </div>
        </div>
    );
}

export default function ChatInstance() {
    const { activeChat, sendMessage, changeEstimateModel, confirmBuild, declineBuild, estimateLoading } = useChatContext();
    const messagesEndRef = useRef<HTMLDivElement>(null);
    const [voiceModeActive, setVoiceModeActive] = useState(false);

    const handleVoiceTranscript = useCallback(
        async (text: string): Promise<string | null> => {
            if (!activeChat) return null;
            return sendMessage(activeChat.id, text);
        },
        [activeChat, sendMessage],
    );

    const voiceEngine = useVoiceEngine(handleVoiceTranscript);

    useEffect(() => {
        messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
    }, [activeChat?.messages.length]);

    if (!activeChat) return null;

    const handleSend = (content: string) => {
        sendMessage(activeChat.id, content);
    };

    const toggleVoiceMode = async () => {
        if (voiceEngine.isActive) {
            voiceEngine.stopConversation();
            setVoiceModeActive(false);
        } else {
            await voiceEngine.startConversation();
            setVoiceModeActive(true);
        }
    };

    return (
        <div className="chat-instance">
            {/* Top bar */}
            <div className="top-bar">
                <span className="top-bar__title">Telos</span>
                <button
                    className={`voice-toggle-btn ${voiceModeActive ? "active" : ""}`}
                    onClick={toggleVoiceMode}
                    title={voiceModeActive ? "Stop voice mode" : "Start voice mode"}
                    type="button"
                >
                    {voiceModeActive ? (
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
                            <rect x="6" y="6" width="12" height="12" rx="2" />
                        </svg>
                    ) : (
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                            <path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z" />
                            <path d="M19 10v2a7 7 0 0 1-14 0v-2" />
                            <line x1="12" y1="19" x2="12" y2="23" />
                            <line x1="8" y1="23" x2="16" y2="23" />
                        </svg>
                    )}
                    <span>{voiceModeActive ? "End" : "Voice"}</span>
                </button>
            </div>

            {/* Voice Orb */}
            {voiceModeActive && (
                <div className="voice-orb-section">
                    <VoiceOrb mode={voiceEngine.mode} audioLevel={voiceEngine.audioLevel} />
                    {voiceEngine.transcript && (
                        <p className="voice-transcript">&ldquo;{voiceEngine.transcript}&rdquo;</p>
                    )}
                </div>
            )}

            {/* Messages */}
            <div className={`messages-area ${voiceModeActive ? "messages-area--compact" : ""}`}>
                {activeChat.messages.map((msg) => (
                    <div
                        key={msg.id}
                        className={`message message--${msg.role}`}
                    >
                        <div className="message__role">
                            {msg.role === "user" ? "You" : "Telos"}
                        </div>
                        <div className="message__content">{msg.content}</div>
                    </div>
                ))}
                <div ref={messagesEndRef} />
            </div>

            {/* Progress bar — shown during planning and building */}
            {(activeChat.phase === "planning" || activeChat.phase === "building") && (
                <BuildProgressBar
                    phase={activeChat.phase}
                    prdProgress={activeChat.prdProgress}
                />
            )}

            {/* Cost estimate confirmation */}
            {activeChat.phase === "confirming" && activeChat.costEstimate && (
                <div className="cost-estimate-wrapper">
                    <CostEstimate
                        estimate={activeChat.costEstimate}
                        loading={estimateLoading}
                        onModelChange={(model) => changeEstimateModel(activeChat.id, model)}
                        onConfirm={() => confirmBuild(activeChat.id)}
                        onDecline={() => declineBuild(activeChat.id)}
                    />
                </div>
            )}

            {/* Cost tracker — shown during build when estimate was accepted */}
            {(activeChat.phase === "building" || activeChat.phase === "done") && activeChat.costEstimate && (
                <BuildCostTracker
                    estimate={activeChat.costEstimate}
                    currentIteration={activeChat.buildIteration}
                    phase={activeChat.phase === "building" ? "building" : "done"}
                    prdCount={activeChat.prdProgress?.prds.length}
                />
            )}

            {/* PRD progress — shown during build when PRDs exist */}
            {(activeChat.phase === "building" || activeChat.phase === "done") && activeChat.prdProgress && (
                <PrdProgressPanel progress={activeChat.prdProgress} />
            )}

            {/* Input at bottom — only during conversation */}
            {!voiceModeActive && activeChat.phase === "conversation" && (
                <div className="chat-instance__input">
                    <ChatInputBar onSend={handleSend} autoFocus placeholder="Follow up…" />
                </div>
            )}
        </div>
    );
}
