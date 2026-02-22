"use client";

import ChatInputBar from "./ChatInputBar";
import { useChatContext } from "./ChatContext";

export default function ChatHome() {
    const { createChat } = useChatContext();

    const handleSend = (message: string) => {
        createChat(message);
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
            <p className="chat-hint">Create your first project</p>
        </div>
    );
}
