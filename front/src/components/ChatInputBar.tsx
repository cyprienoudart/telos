"use client";

import { useState, useRef, useEffect } from "react";
import MicButton from "./MicButton";

interface ChatInputBarProps {
    onSend: (message: string) => void;
    placeholder?: string;
    autoFocus?: boolean;
    disabled?: boolean;
}

export default function ChatInputBar({ onSend, placeholder = "Ask me anything...", autoFocus = false, disabled = false }: ChatInputBarProps) {
    const [value, setValue] = useState("");
    const textareaRef = useRef<HTMLTextAreaElement>(null);

    useEffect(() => {
        if (autoFocus && textareaRef.current) {
            textareaRef.current.focus();
        }
    }, [autoFocus]);

    const handleInput = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
        setValue(e.target.value);
        // Auto-resize
        const ta = e.target;
        ta.style.height = "auto";
        ta.style.height = Math.min(ta.scrollHeight, 120) + "px";
    };

    const handleSend = () => {
        const trimmed = value.trim();
        if (!trimmed || disabled) return;
        onSend(trimmed);
        setValue("");
        if (textareaRef.current) {
            textareaRef.current.style.height = "auto";
        }
    };

    const handleKeyDown = (e: React.KeyboardEvent) => {
        if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault();
            handleSend();
        }
    };

    const handleTranscript = (text: string) => {
        setValue((prev) => prev + text);
    };

    const isEmpty = value.trim().length === 0;

    return (
        <div className="chat-input-wrapper">
            <div className="chat-input-container">
                <textarea
                    ref={textareaRef}
                    className="chat-input"
                    value={value}
                    onChange={handleInput}
                    onKeyDown={handleKeyDown}
                    placeholder={placeholder}
                    rows={1}
                    disabled={disabled}
                />
                <div className="chat-input-actions">
                    <MicButton onTranscript={handleTranscript} />
                    <button
                        className="send-btn"
                        onClick={handleSend}
                        disabled={isEmpty || disabled}
                        title="Send message"
                        type="button"
                    >
                        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                            <path d="M5 12h14" />
                            <path d="m12 5 7 7-7 7" />
                        </svg>
                    </button>
                </div>
            </div>
        </div>
    );
}
