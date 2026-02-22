"use client";

import { useState, useRef } from "react";
import ChatInputBar from "./ChatInputBar";
import { useChatContext } from "./ChatContext";

export default function ChatHome() {
    const { createChat } = useChatContext();
    const [files, setFiles] = useState<File[]>([]);
    const [githubUrl, setGithubUrl] = useState("");
    const [isProcessing, setIsProcessing] = useState(false);
    const fileInputRef = useRef<HTMLInputElement>(null);

    const handleSend = async (message: string) => {
        setIsProcessing(true);
        try {
            await createChat(message, files.length > 0 ? files : undefined, githubUrl || undefined);
        } finally {
            setIsProcessing(false);
        }
    };

    const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
        if (e.target.files) {
            setFiles((prev) => [...prev, ...Array.from(e.target.files!)]);
        }
        // Reset input so the same file can be re-selected
        e.target.value = "";
    };

    const removeFile = (index: number) => {
        setFiles((prev) => prev.filter((_, i) => i !== index));
    };

    const formatFileSize = (bytes: number) => {
        if (bytes < 1024) return `${bytes} B`;
        if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
        return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
    };

    return (
        <div className="chat-home">
            <img
                src="/Telos logo-Photoroom.png"
                alt="Telos"
                className="chat-home__logo"
            />
            <h1 className="chat-home__greeting">Welcome, ready to make agents truly agentic?</h1>

            {/* File chips */}
            {files.length > 0 && (
                <div className="file-chips">
                    {files.map((file, i) => (
                        <div key={`${file.name}-${i}`} className="file-chip">
                            <svg className="file-chip__icon" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                                <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
                                <polyline points="14 2 14 8 20 8" />
                            </svg>
                            <span className="file-chip__name">{file.name}</span>
                            <span className="file-chip__size">{formatFileSize(file.size)}</span>
                            <button
                                className="file-chip__remove"
                                onClick={() => removeFile(i)}
                                title="Remove file"
                                type="button"
                            >
                                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                                    <line x1="18" y1="6" x2="6" y2="18" />
                                    <line x1="6" y1="6" x2="18" y2="18" />
                                </svg>
                            </button>
                        </div>
                    ))}
                </div>
            )}

            <ChatInputBar onSend={handleSend} autoFocus placeholder="Describe your first project..." disabled={isProcessing} />

            {/* Actions row: attach files + GitHub link */}
            <div className="home-actions">
                {/* Hidden file input */}
                <input
                    ref={fileInputRef}
                    type="file"
                    multiple
                    accept="image/*,.pdf,.txt,.md,.json,.csv,.xml,.html,.css,.js,.ts,.py,.java,.go,.rs,.rb,.php"
                    onChange={handleFileSelect}
                    style={{ display: "none" }}
                />

                <button
                    className="home-action-btn"
                    onClick={() => fileInputRef.current?.click()}
                    title="Attach files (images, PDFs, documents)"
                    type="button"
                    disabled={isProcessing}
                >
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                        <path d="M21.44 11.05l-9.19 9.19a6 6 0 0 1-8.49-8.49l9.19-9.19a4 4 0 0 1 5.66 5.66l-9.2 9.19a2 2 0 0 1-2.83-2.83l8.49-8.48" />
                    </svg>
                    <span>Attach files</span>
                </button>

                <div className="github-input-wrapper">
                    <svg className="github-input-icon" width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
                        <path d="M12 0C5.37 0 0 5.37 0 12c0 5.31 3.435 9.795 8.205 11.385.6.105.825-.255.825-.57 0-.285-.015-1.23-.015-2.235-3.015.555-3.795-.735-4.035-1.41-.135-.345-.72-1.41-1.23-1.695-.42-.225-1.02-.78-.015-.795.945-.015 1.62.87 1.845 1.23 1.08 1.815 2.805 1.305 3.495.99.105-.78.42-1.305.765-1.605-2.67-.3-5.46-1.335-5.46-5.925 0-1.305.465-2.385 1.23-3.225-.12-.3-.54-1.53.12-3.18 0 0 1.005-.315 3.3 1.23.96-.27 1.98-.405 3-.405s2.04.135 3 .405c2.295-1.56 3.3-1.23 3.3-1.23.66 1.65.24 2.88.12 3.18.765.84 1.23 1.905 1.23 3.225 0 4.605-2.805 5.625-5.475 5.925.435.375.81 1.095.81 2.22 0 1.605-.015 2.895-.015 3.3 0 .315.225.69.825.57A12.02 12.02 0 0 0 24 12c0-6.63-5.37-12-12-12z" />
                    </svg>
                    <input
                        className="github-input"
                        type="url"
                        placeholder="GitHub repo URL (optional)"
                        value={githubUrl}
                        onChange={(e) => setGithubUrl(e.target.value)}
                        disabled={isProcessing}
                    />
                </div>
            </div>

            {/* Processing indicator */}
            {isProcessing && (
                <div className="processing-indicator">
                    <div className="processing-spinner" />
                    <span>Processing your files...</span>
                </div>
            )}

            {!isProcessing && <p className="chat-hint">Create your first project</p>}
        </div>
    );
}
