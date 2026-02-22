"use client";

import { ChatProvider, useChatContext } from "./ChatContext";
import ChatHome from "./ChatHome";
import ChatInstance from "./ChatInstance";
import Sidebar from "./Sidebar";

function ChatAppInner() {
    const { activeChatId } = useChatContext();

    return (
        <div className="app-layout">
            <div className="main-area">
                {activeChatId ? <ChatInstance /> : <ChatHome />}
            </div>
            <Sidebar />
        </div>
    );
}

export default function ChatApp() {
    return (
        <ChatProvider>
            <ChatAppInner />
        </ChatProvider>
    );
}
