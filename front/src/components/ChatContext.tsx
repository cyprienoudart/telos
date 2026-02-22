"use client";

import {
    createContext,
    useContext,
    useState,
    useCallback,
    type ReactNode,
} from "react";

export interface Message {
    id: string;
    role: "user" | "ai";
    content: string;
    timestamp: Date;
}

export interface Chat {
    id: string;
    title: string;
    messages: Message[];
    createdAt: Date;
}

interface ChatContextType {
    chats: Chat[];
    activeChatId: string | null;
    activeChat: Chat | null;
    createChat: (firstMessage: string) => string;
    sendMessage: (chatId: string, content: string) => void;
    setActiveChatId: (id: string | null) => void;
    goHome: () => void;
}

const ChatContext = createContext<ChatContextType | null>(null);

export function useChatContext() {
    const ctx = useContext(ChatContext);
    if (!ctx) throw new Error("useChatContext must be inside ChatProvider");
    return ctx;
}

function generateId() {
    return Math.random().toString(36).substring(2, 10) + Date.now().toString(36);
}

export function ChatProvider({ children }: { children: ReactNode }) {
    const [chats, setChats] = useState<Chat[]>([]);
    const [activeChatId, setActiveChatId] = useState<string | null>(null);

    const activeChat = chats.find((c) => c.id === activeChatId) || null;

    const createChat = useCallback(
        (firstMessage: string) => {
            const chatId = generateId();
            const userMsg: Message = {
                id: generateId(),
                role: "user",
                content: firstMessage,
                timestamp: new Date(),
            };

            const newChat: Chat = {
                id: chatId,
                title: firstMessage.length > 40 ? firstMessage.slice(0, 40) + "…" : firstMessage,
                messages: [userMsg],
                createdAt: new Date(),
            };

            setChats((prev) => [newChat, ...prev]);
            setActiveChatId(chatId);

            // Simulate AI response
            setTimeout(() => {
                const aiMsg: Message = {
                    id: generateId(),
                    role: "ai",
                    content: "I've received your request. I'm processing it and will route it to the right agent. This is where the AI response will appear once the backend is connected.",
                    timestamp: new Date(),
                };
                setChats((prev) =>
                    prev.map((c) =>
                        c.id === chatId ? { ...c, messages: [...c.messages, aiMsg] } : c
                    )
                );
            }, 1500);

            return chatId;
        },
        []
    );

    const sendMessage = useCallback(
        (chatId: string, content: string) => {
            const userMsg: Message = {
                id: generateId(),
                role: "user",
                content,
                timestamp: new Date(),
            };

            setChats((prev) =>
                prev.map((c) =>
                    c.id === chatId ? { ...c, messages: [...c.messages, userMsg] } : c
                )
            );

            // Simulate AI reply
            setTimeout(() => {
                const aiMsg: Message = {
                    id: generateId(),
                    role: "ai",
                    content: "Thanks for your follow-up. I'm analyzing your input and preparing the optimal response. Backend integration coming soon.",
                    timestamp: new Date(),
                };
                setChats((prev) =>
                    prev.map((c) =>
                        c.id === chatId ? { ...c, messages: [...c.messages, aiMsg] } : c
                    )
                );
            }, 1200);
        },
        []
    );

    const goHome = useCallback(() => {
        setActiveChatId(null);
    }, []);

    return (
        <ChatContext.Provider
            value={{
                chats,
                activeChatId,
                activeChat,
                createChat,
                sendMessage,
                setActiveChatId,
                goHome,
            }}
        >
            {children}
        </ChatContext.Provider>
    );
}
