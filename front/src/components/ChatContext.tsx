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

export interface Message {
    id: string;
    role: "user" | "ai";
    content: string;
    timestamp: Date;
}

export type ChatPhase = "conversation" | "building" | "done";

export interface TrajectoryEvent {
    type: string;
    [key: string]: unknown;
}

export interface Chat {
    id: string;
    title: string;
    messages: Message[];
    trajectory: TrajectoryEvent[];
    createdAt: Date;
    sessionId: string | null;
    buildId: string | null;
    phase: ChatPhase;
    repoUrl: string | null;
    repoDir: string | null;
}

interface ChatContextType {
    chats: Chat[];
    activeChatId: string | null;
    activeChat: Chat | null;
    createChat: (firstMessage: string, githubUrl?: string) => Promise<string>;
    sendMessage: (chatId: string, content: string) => Promise<string | null>;
    debugBuild: () => Promise<void>;
    resetAll: () => Promise<void>;
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
        async (firstMessage: string, githubUrl?: string): Promise<string> => {
            const chatId = generateId();
            const userMsg: Message = {
                id: generateId(),
                role: "user",
                content: firstMessage,
                timestamp: new Date(),
            };

            const newChat: Chat = {
                id: chatId,
                title:
                    firstMessage.length > 40
                        ? firstMessage.slice(0, 40) + "\u2026"
                        : firstMessage,
                messages: [userMsg],
                trajectory: [],
                createdAt: new Date(),
                sessionId: null,
                buildId: null,
                phase: "conversation",
                repoUrl: githubUrl ?? null,
                repoDir: null,
            };

            setChats((prev) => [newChat, ...prev]);
            setActiveChatId(chatId);

            try {
                const body: Record<string, string> = { message: firstMessage };
                if (githubUrl) body.github_url = githubUrl;

                const res = await fetch("/api/backend/conversation/start", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify(body),
                });

                if (!res.ok) {
                    addMessage(setChats, chatId, "ai", "Failed to reach the server. Please try again.");
                    return chatId;
                }

                const data = await res.json();

                // Attach session ID + repo info
                setChats((prev) =>
                    prev.map((c) =>
                        c.id === chatId
                            ? {
                                  ...c,
                                  sessionId: data.session_id,
                                  repoUrl: data.repo_url ?? null,
                                  repoDir: data.repo_dir ?? null,
                              }
                            : c
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
                    let meta = "";
                    if (data.repo_url && data.rag_answered_count > 0) {
                        const repoName = data.repo_url.replace(/^https:\/\/github\.com\//, "");
                        meta = `Connected: ${repoName}. I pre-answered ${data.rag_answered_count} items from the codebase. `;
                    } else if (data.rag_answered_count > 0) {
                        meta = `I pre-answered ${data.rag_answered_count} items from your files. `;
                    } else if (data.repo_url) {
                        const repoName = data.repo_url.replace(/^https:\/\/github\.com\//, "");
                        meta = `Connected: ${repoName}. `;
                    }
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
                    body: JSON.stringify({ session_id: sessionId }),
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

            // Batch trajectory events to avoid excessive re-renders
            let pendingEvents: TrajectoryEvent[] = [];
            let rafScheduled = false;

            const flushEvents = () => {
                if (pendingEvents.length === 0) return;
                const batch = pendingEvents;
                pendingEvents = [];
                rafScheduled = false;
                setChats((prev) =>
                    prev.map((c) =>
                        c.id === chatId
                            ? { ...c, trajectory: [...c.trajectory, ...batch] }
                            : c
                    )
                );
            };

            source.addEventListener("trajectory", (e) => {
                try {
                    const evt: TrajectoryEvent = JSON.parse(e.data);
                    pendingEvents.push(evt);
                    if (!rafScheduled) {
                        rafScheduled = true;
                        requestAnimationFrame(flushEvents);
                    }
                } catch {
                    // skip malformed events
                }
            });

            source.addEventListener("progress", (e) => {
                addMessage(setChats, chatId, "ai", e.data);
            });

            source.addEventListener("done", (e) => {
                // Flush any remaining trajectory events
                flushEvents();
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

    // ── Debug Build (skip interview, use fixture) ─────────────────────

    const debugBuild = useCallback(async () => {
        const chatId = generateId();
        const infoMsg: Message = {
            id: generateId(),
            role: "ai",
            content: "Debug mode — skipping interview, using test fixture. Starting build...",
            timestamp: new Date(),
        };

        const newChat: Chat = {
            id: chatId,
            title: "Debug Build",
            messages: [infoMsg],
            trajectory: [],
            createdAt: new Date(),
            sessionId: null,
            buildId: null,
            phase: "building",
            repoUrl: null,
            repoDir: null,
        };

        setChats((prev) => [newChat, ...prev]);
        setActiveChatId(chatId);

        try {
            const res = await fetch("/api/backend/build/debug-start", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({}),
            });

            if (!res.ok) {
                const errText = await res.text();
                addMessage(setChats, chatId, "ai", `Debug build failed: ${errText}`);
                setChats((prev) =>
                    prev.map((c) =>
                        c.id === chatId ? { ...c, phase: "done" } : c
                    )
                );
                return;
            }

            const data = await res.json();
            setChats((prev) =>
                prev.map((c) =>
                    c.id === chatId ? { ...c, buildId: data.build_id } : c
                )
            );

            streamBuildProgress(chatId, data.build_id);
        } catch {
            addMessage(setChats, chatId, "ai", "Failed to start debug build.");
            setChats((prev) =>
                prev.map((c) =>
                    c.id === chatId ? { ...c, phase: "done" } : c
                )
            );
        }
    }, [streamBuildProgress]);

    // ── Reset All (demo cleanup) ──────────────────────────────────

    const resetAll = useCallback(async () => {
        // Clear backend sessions and builds in parallel
        await Promise.allSettled([
            fetch("/api/backend/conversation/reset", { method: "POST" }),
            fetch("/api/backend/build/reset", { method: "POST" }),
        ]);
        // Clear frontend state
        setChats([]);
        setActiveChatId(null);
        questionInfoRef.current = {};
    }, []);

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
                debugBuild,
                resetAll,
                setActiveChatId,
                goHome,
            }}
        >
            {children}
        </ChatContext.Provider>
    );
}
