"use client";

import { useState } from "react";
import ChatInputBar from "./ChatInputBar";
import { useChatContext } from "./ChatContext";

export default function ChatHome() {
    const { createChat, debugBuild } = useChatContext();
    const [showRepoInput, setShowRepoInput] = useState(false);
    const [githubUrl, setGithubUrl] = useState("");

    const handleSend = (message: string) => {
        createChat(message, githubUrl || undefined);
    };

    return (
        <div className="chat-home">
            <img
                src="/Telos logo-Photoroom.png"
                alt="Telos"
                className="chat-home__logo"
            />
            <h1 className="chat-home__greeting">Welcome, ready to make agents truly agentic?</h1>
            <ChatInputBar onSend={handleSend} autoFocus placeholder="Describe your first project..." />

            {!showRepoInput ? (
                <button
                    className="repo-link"
                    onClick={() => setShowRepoInput(true)}
                >
                    Connect a GitHub repo
                </button>
            ) : (
                <div className="repo-input-wrapper">
                    <input
                        type="url"
                        className="repo-input"
                        placeholder="https://github.com/owner/repo"
                        value={githubUrl}
                        onChange={(e) => setGithubUrl(e.target.value)}
                        autoFocus
                    />
                    {githubUrl && (
                        <button
                            className="repo-clear"
                            onClick={() => { setGithubUrl(""); setShowRepoInput(false); }}
                            aria-label="Remove repo"
                        >
                            &times;
                        </button>
                    )}
                </div>
            )}

            <p className="chat-hint">Create your first project</p>

            <button
                className="debug-build-btn"
                onClick={debugBuild}
                title="Skip interview — use test/fixtures/debug_context.md"
            >
                Debug Build
            </button>
        </div>
    );
}
