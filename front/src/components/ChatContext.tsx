"use client";

import {
    createContext,
    useContext,
    useState,
    useCallback,
    useRef,
    type Dispatch,
    type SetStateAction,
    type ReactNode,
} from "react";

// ── Types ────────────────────────────────────────────────────────────────

export interface MessageAttachment {
    name: string;
    size: number;
}

export interface Message {
    id: string;
    role: "user" | "ai";
    content: string;
    timestamp: Date;
    attachments?: MessageAttachment[];
    githubUrl?: string;
}

export type ChatPhase = "conversation" | "building" | "done";

export interface Chat {
    id: string;
    title: string;
    messages: Message[];
    createdAt: Date;
    sessionId: string | null;
    buildId: string | null;
    phase: ChatPhase;
}

interface ChatContextType {
    chats: Chat[];
    activeChatId: string | null;
    activeChat: Chat | null;
    createChat: (firstMessage: string, files?: File[], githubUrl?: string) => Promise<string>;
    sendMessage: (chatId: string, content: string) => Promise<string | null>;
    setActiveChatId: (id: string | null) => void;
    goHome: () => void;
}

const ChatContext = createContext<ChatContextType | null>(null);

export function useChatContext() {
    const ctx = useContext(ChatContext);
    if (!ctx) throw new Error("useChatContext must be inside ChatProvider");
    return ctx;
}

// ── Helpers ──────────────────────────────────────────────────────────────

function generateId() {
    return Math.random().toString(36).substring(2, 10) + Date.now().toString(36);
}

function addMessage(
    setChats: Dispatch<SetStateAction<Chat[]>>,
    chatId: string,
    role: "user" | "ai",
    content: string,
) {
    const msg: Message = { id: generateId(), role, content, timestamp: new Date() };
    setChats((prev) =>
        prev.map((c) =>
            c.id === chatId ? { ...c, messages: [...c.messages, msg] } : c
        )
    );
}

// ── Provider ─────────────────────────────────────────────────────────────

export function ChatProvider({ children }: { children: ReactNode }) {
    const [chats, setChats] = useState<Chat[]>([]);
    const [activeChatId, setActiveChatId] = useState<string | null>(null);

    // Refs to avoid stale closures in callbacks
    const questionInfoRef = useRef<Record<string, string | null>>({});
    const chatsRef = useRef(chats);
    chatsRef.current = chats;

    const activeChat = chats.find((c) => c.id === activeChatId) || null;

    // ── Create Chat (POST /api/backend/conversation/start) ───────────

    const createChat = useCallback(
        async (firstMessage: string, files?: File[], githubUrl?: string): Promise<string> => {
            const chatId = generateId();
            const userMsg: Message = {
                id: generateId(),
                role: "user",
                content: firstMessage,
                timestamp: new Date(),
                attachments: files && files.length > 0
                    ? files.map((f) => ({ name: f.name, size: f.size }))
                    : undefined,
                githubUrl: githubUrl || undefined,
            };

            const newChat: Chat = {
                id: chatId,
                title:
                    firstMessage.length > 40
                        ? firstMessage.slice(0, 40) + "\u2026"
                        : firstMessage,
                messages: [userMsg],
                createdAt: new Date(),
                sessionId: null,
                buildId: null,
                phase: "conversation",
            };

            setChats((prev) => [newChat, ...prev]);
            setActiveChatId(chatId);

            try {
                // Step 1: Process uploaded files via Gemini multimodal (if any)
                let additionalContext: string | null = null;
                let filesDir: string | null = null;
                if (files && files.length > 0) {
                    try {
                        const formData = new FormData();
                        for (const file of files) {
                            formData.append("files", file);
                        }
                        const uploadRes = await fetch("/api/backend/context/process", {
                            method: "POST",
                            body: formData,
                        });
                        if (uploadRes.ok) {
                            const uploadData = await uploadRes.json();
                            if (uploadData.extracted_text) {
                                additionalContext = uploadData.extracted_text;
                            }
                            if (uploadData.files_dir) {
                                filesDir = uploadData.files_dir;
                            }
                        }
                    } catch {
                        // File processing failed — continue without it
                    }
                }

                // Step 2: Start the conversation with message + optional context
                const startBody: Record<string, string> = { message: firstMessage };
                if (additionalContext) {
                    startBody.additional_context = additionalContext;
                }
                if (githubUrl) {
                    startBody.github_url = githubUrl;
                }
                if (filesDir) {
                    startBody.files_dir = filesDir;
                }

                const res = await fetch("/api/backend/conversation/start", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify(startBody),
                });

                if (!res.ok) {
                    addMessage(setChats, chatId, "ai", "Failed to reach the server. Please try again.");
                    return chatId;
                }

                const data = await res.json();

                // Attach session ID
                setChats((prev) =>
                    prev.map((c) =>
                        c.id === chatId ? { ...c, sessionId: data.session_id } : c
                    )
                );

                if (data.done) {
                    // Enough context already — trigger build
                    addMessage(
                        setChats,
                        chatId,
                        "ai",
                        `Great, I have everything I need from your description! Coverage: ${Math.round(data.initial_coverage * 100)}%. Starting the build\u2026`,
                    );
                    setChats((prev) =>
                        prev.map((c) =>
                            c.id === chatId ? { ...c, phase: "building" } : c
                        )
                    );
                    triggerBuild(chatId, data.session_id);
                } else if (data.first_question) {
                    const meta = data.rag_answered_count > 0
                        ? `I pre-answered ${data.rag_answered_count} items from your files. `
                        : "";
                    addMessage(setChats, chatId, "ai", meta + data.first_question);
                    questionInfoRef.current[chatId] = data.first_question;
                }
            } catch {
                addMessage(setChats, chatId, "ai", "Could not connect to the server.");
            }

            return chatId;
        },
        [],
    );

    // ── Send Message (POST /api/backend/conversation/{sessionId}/answer) ──

    const sendMessage = useCallback(
        async (chatId: string, content: string): Promise<string | null> => {
            addMessage(setChats, chatId, "user", content);

            const chat = chatsRef.current.find((c) => c.id === chatId);
            if (!chat?.sessionId) {
                addMessage(setChats, chatId, "ai", "No active session.");
                return null;
            }

            try {
                const res = await fetch(
                    `/api/backend/conversation/${chat.sessionId}/answer`,
                    {
                        method: "POST",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify({ answer: content }),
                    },
                );

                if (!res.ok) {
                    addMessage(setChats, chatId, "ai", "Server error. Please try again.");
                    return null;
                }

                const data = await res.json();

                if (data.done) {
                    const finalCoverage = Math.round(data.coverage * 100);
                    addMessage(
                        setChats,
                        chatId,
                        "ai",
                        `I have everything I need! Coverage: ${finalCoverage}%. Starting the build\u2026`,
                    );
                    setChats((prev) =>
                        prev.map((c) =>
                            c.id === chatId ? { ...c, phase: "building" } : c
                        )
                    );
                    triggerBuild(chatId, chat.sessionId);
                    return null;
                } else if (data.next_question) {
                    const resolvedNote =
                        data.resolved.length > 0
                            ? `Got it (${data.resolved.length} resolved). `
                            : "";
                    const aiText = resolvedNote + data.next_question;
                    addMessage(setChats, chatId, "ai", aiText);
                    questionInfoRef.current[chatId] = data.next_question;
                    return aiText;
                }
            } catch {
                addMessage(setChats, chatId, "ai", "Connection lost. Please try again.");
            }
            return null;
        },
        [],
    );

    // ── Trigger Build ────────────────────────────────────────────────

    const triggerBuild = useCallback(
        async (chatId: string, sessionId: string) => {
            try {
                const res = await fetch("/api/backend/build/start", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({
                        session_id: sessionId,
                        project_dir: `/tmp/telos-build-${sessionId}`,
                    }),
                });

                if (!res.ok) {
                    addMessage(setChats, chatId, "ai", "Failed to start build.");
                    return;
                }

                const data = await res.json();
                setChats((prev) =>
                    prev.map((c) =>
                        c.id === chatId ? { ...c, buildId: data.build_id } : c
                    )
                );

                // Open SSE stream for progress
                streamBuildProgress(chatId, data.build_id);
            } catch {
                addMessage(setChats, chatId, "ai", "Failed to start build.");
            }
        },
        [],
    );

    // ── SSE Build Progress Stream ────────────────────────────────────

    const streamBuildProgress = useCallback(
        (chatId: string, buildId: string) => {
            const source = new EventSource(`/api/backend/build/${buildId}/stream`);

            source.addEventListener("progress", (e) => {
                addMessage(setChats, chatId, "ai", e.data);
            });

            source.addEventListener("done", (e) => {
                try {
                    const data = JSON.parse(e.data);
                    const status = data.success ? "Build completed!" : `Build failed: ${data.error}`;
                    addMessage(setChats, chatId, "ai", status);
                } catch {
                    addMessage(setChats, chatId, "ai", "Build finished.");
                }
                setChats((prev) =>
                    prev.map((c) =>
                        c.id === chatId ? { ...c, phase: "done" } : c
                    )
                );
                source.close();
            });

            source.onerror = () => {
                source.close();
            };
        },
        [],
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
