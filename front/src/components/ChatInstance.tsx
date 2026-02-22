"use client";

import { useEffect, useRef, useState, useCallback } from "react";
import { useChatContext } from "./ChatContext";
import type { Message } from "./ChatContext";
import ChatInputBar from "./ChatInputBar";
import VoiceOrb from "./VoiceOrb";
import { useVoiceEngine } from "@/hooks/useVoiceEngine";

function formatFileSize(bytes: number) {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function MessageAttachments({ msg }: { msg: Message }) {
    const hasAttachments = msg.attachments && msg.attachments.length > 0;
    const hasGithub = !!msg.githubUrl;
    if (!hasAttachments && !hasGithub) return null;

    return (
        <div className="message-attachments">
            {hasAttachments && (
                <div className="message-file-chips">
                    {msg.attachments!.map((att, i) => (
                        <div key={`${att.name}-${i}`} className="file-chip file-chip--inline">
                            <svg className="file-chip__icon" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                                <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
                                <polyline points="14 2 14 8 20 8" />
                            </svg>
                            <span className="file-chip__name">{att.name}</span>
                            <span className="file-chip__size">{formatFileSize(att.size)}</span>
                        </div>
                    ))}
                </div>
            )}
            {hasGithub && (
                <a
                    className="github-chip"
                    href={msg.githubUrl}
                    target="_blank"
                    rel="noopener noreferrer"
                >
                    <svg className="github-chip__icon" width="14" height="14" viewBox="0 0 24 24" fill="currentColor">
                        <path d="M12 0C5.37 0 0 5.37 0 12c0 5.31 3.435 9.795 8.205 11.385.6.105.825-.255.825-.57 0-.285-.015-1.23-.015-2.235-3.015.555-3.795-.735-4.035-1.41-.135-.345-.72-1.41-1.23-1.695-.42-.225-1.02-.78-.015-.795.945-.015 1.62.87 1.845 1.23 1.08 1.815 2.805 1.305 3.495.99.105-.78.42-1.305.765-1.605-2.67-.3-5.46-1.335-5.46-5.925 0-1.305.465-2.385 1.23-3.225-.12-.3-.54-1.53.12-3.18 0 0 1.005-.315 3.3 1.23.96-.27 1.98-.405 3-.405s2.04.135 3 .405c2.295-1.56 3.3-1.23 3.3-1.23.66 1.65.24 2.88.12 3.18.765.84 1.23 1.905 1.23 3.225 0 4.605-2.805 5.625-5.475 5.925.435.375.81 1.095.81 2.22 0 1.605-.015 2.895-.015 3.3 0 .315.225.69.825.57A12.02 12.02 0 0 0 24 12c0-6.63-5.37-12-12-12z" />
                    </svg>
                    <span className="github-chip__url">{msg.githubUrl!.replace(/^https?:\/\/(www\.)?github\.com\//, "")}</span>
                    <svg className="github-chip__external" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                        <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6" />
                        <polyline points="15 3 21 3 21 9" />
                        <line x1="10" y1="14" x2="21" y2="3" />
                    </svg>
                </a>
            )}
        </div>
    );
}

export default function ChatInstance() {
    const { activeChat, sendMessage } = useChatContext();
    const messagesEndRef = useRef<HTMLDivElement>(null);
    const [voiceModeActive, setVoiceModeActive] = useState(false);

    // Voice transcript → backend → AI response → TTS
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

            {/* Voice Orb — shown when voice mode is active */}
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
                        <MessageAttachments msg={msg} />
                    </div>
                ))}
                <div ref={messagesEndRef} />
            </div>

            {/* Input at bottom */}
            {!voiceModeActive && (
                <div className="chat-instance__input">
                    <ChatInputBar onSend={handleSend} autoFocus placeholder="Follow up…" />
                </div>
            )}
        </div>
    );
}
