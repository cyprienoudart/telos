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

export type ChatPhase = "conversation" | "planning" | "confirming" | "building" | "done";

export interface CostEstimateData {
    low_usd: number;
    typical_usd: number;
    high_usd: number;
    model: string;
    max_iterations: number;
    estimated_prd_count: number;
    breakdown: {
        phase: string;
        input_tokens: number;
        output_tokens: number;
        model: string;
        cost_usd: number;
    }[];
}

export interface PrdCheckboxItem {
    text: string;
    checked: boolean;
}

export interface PrdProgress {
    filename: string;
    title: string;
    items: PrdCheckboxItem[];
    total: number;
    done: number;
    percent: number;
}

export interface PrdProgressData {
    build_id: string;
    prds: PrdProgress[];
    total_items: number;
    total_done: number;
    overall_percent: number;
}

export interface Chat {
    id: string;
    title: string;
    messages: Message[];
    createdAt: Date;
    sessionId: string | null;
    buildId: string | null;
    phase: ChatPhase;
    repoUrl: string | null;
    repoDir: string | null;
    costEstimate: CostEstimateData | null;
    buildIteration: number;
    prdProgress: PrdProgressData | null;
}

interface ChatContextType {
    chats: Chat[];
    activeChatId: string | null;
    activeChat: Chat | null;
    estimateLoading: boolean;
    createChat: (firstMessage: string, githubUrl?: string) => Promise<string>;
    sendMessage: (chatId: string, content: string) => Promise<string | null>;
    changeEstimateModel: (chatId: string, model: string) => void;
    confirmBuild: (chatId: string) => void;
    declineBuild: (chatId: string) => void;
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
    const [estimateLoading, setEstimateLoading] = useState(false);

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
                createdAt: new Date(),
                sessionId: null,
                buildId: null,
                phase: "conversation",
                repoUrl: githubUrl ?? null,
                repoDir: null,
                costEstimate: null,
                buildIteration: 0,
                prdProgress: null,
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
                    addMessage(
                        setChats,
                        chatId,
                        "ai",
                        `Great, I have everything I need from your description! Coverage: ${Math.round(data.initial_coverage * 100)}%. Generating plan\u2026`,
                    );
                    setChats((prev) =>
                        prev.map((c) =>
                            c.id === chatId ? { ...c, phase: "planning" } : c
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
                        `I have everything I need! Coverage: ${finalCoverage}%. Generating plan\u2026`,
                    );
                    setChats((prev) =>
                        prev.map((c) =>
                            c.id === chatId ? { ...c, phase: "planning" } : c
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
                const body: Record<string, unknown> = { session_id: sessionId };
                const res = await fetch("/api/backend/build/start", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify(body),
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

                pollBuildStatus(chatId, data.build_id);
            } catch {
                addMessage(setChats, chatId, "ai", "Failed to start build.");
            }
        },
        [],
    );

    // ── Fetch Estimate (POST /api/backend/build/estimate) ──────────

    const fetchEstimate = useCallback(
        async (chatId: string, sessionId: string, model?: string) => {
            setEstimateLoading(true);
            try {
                const body: Record<string, unknown> = { session_id: sessionId };
                if (model) body.model = model;
                const res = await fetch("/api/backend/build/estimate", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify(body),
                });

                if (!res.ok) {
                    addMessage(setChats, chatId, "ai", "Could not estimate cost. You can still start the build.");
                    setChats((prev) =>
                        prev.map((c) =>
                            c.id === chatId ? { ...c, phase: "building" } : c
                        )
                    );
                    triggerBuild(chatId, sessionId);
                    return;
                }

                const estimate = await res.json();
                setChats((prev) =>
                    prev.map((c) =>
                        c.id === chatId
                            ? { ...c, phase: "confirming", costEstimate: estimate }
                            : c
                    )
                );
            } catch {
                addMessage(setChats, chatId, "ai", "Could not estimate cost. Starting build directly.");
                setChats((prev) =>
                    prev.map((c) =>
                        c.id === chatId ? { ...c, phase: "building" } : c
                    )
                );
                triggerBuild(chatId, sessionId);
            } finally {
                setEstimateLoading(false);
            }
        },
        [triggerBuild],
    );

    // ── Build Status Polling ─────────────────────────────────────────

    const pollBuildStatus = useCallback(
        (chatId: string, buildId: string) => {
            let prevPhase = "";

            const poll = async () => {
                try {
                    const res = await fetch(`/api/backend/build/${buildId}/status`);
                    if (!res.ok) return;
                    const data = await res.json();

                    // Update iteration count
                    if (typeof data.iteration === "number") {
                        setChats((prev) =>
                            prev.map((c) =>
                                c.id === chatId ? { ...c, buildIteration: data.iteration } : c
                            )
                        );
                    }

                    // Planning complete → fetch estimate and show confirming
                    if (data.build_phase === "planned" && prevPhase !== "planned") {
                        prevPhase = "planned";
                        try {
                            const estRes = await fetch(`/api/backend/build/${buildId}/estimate`, {
                                method: "POST",
                                headers: { "Content-Type": "application/json" },
                                body: JSON.stringify({ model: "opus" }),
                            });
                            const estimate = estRes.ok ? await estRes.json() : null;
                            setChats((prev) =>
                                prev.map((c) =>
                                    c.id === chatId
                                        ? { ...c, phase: "confirming", costEstimate: estimate }
                                        : c
                                )
                            );
                        } catch {
                            setChats((prev) =>
                                prev.map((c) =>
                                    c.id === chatId ? { ...c, phase: "confirming" } : c
                                )
                            );
                        }
                    }

                    // Executing phase
                    if (data.build_phase === "executing" && prevPhase !== "executing") {
                        prevPhase = "executing";
                    }

                    // Build finished
                    if (data.status === "completed" || data.status === "failed") {
                        clearInterval(interval);
                        const msg = data.success ? "Build completed!" : `Build failed: ${data.error}`;
                        addMessage(setChats, chatId, "ai", msg);
                        // Final PRD fetch
                        try {
                            const prdRes = await fetch(`/api/backend/build/${buildId}/prds`);
                            if (prdRes.ok) {
                                const prdData = await prdRes.json();
                                setChats((prev) =>
                                    prev.map((c) =>
                                        c.id === chatId ? { ...c, prdProgress: prdData } : c
                                    )
                                );
                            }
                        } catch { /* ignore */ }
                        setChats((prev) =>
                            prev.map((c) =>
                                c.id === chatId ? { ...c, phase: "done" } : c
                            )
                        );
                    }
                } catch {
                    // silently skip failed polls
                }
            };

            // Immediate first poll
            poll();
            const interval = setInterval(poll, 3000);
            return interval;
        },
        [],
    );

    // ── PRD Progress Polling ──────────────────────────────────────────

    const pollPrdProgress = useCallback(
        (chatId: string, buildId: string) => {
            const fetchProgress = async () => {
                try {
                    const res = await fetch(`/api/backend/build/${buildId}/prds`);
                    if (!res.ok) return;
                    const data = await res.json();
                    setChats((prev) =>
                        prev.map((c) =>
                            c.id === chatId ? { ...c, prdProgress: data } : c
                        )
                    );
                } catch {
                    // silently skip failed polls
                }
            };

            // Immediate first fetch
            fetchProgress();

            const interval = setInterval(() => {
                const chat = chatsRef.current.find((c) => c.id === chatId);
                if (chat?.phase === "done") {
                    clearInterval(interval);
                    fetchProgress();
                    return;
                }
                fetchProgress();
            }, 3000);

            return interval;
        },
        [],
    );

    // ── Debug Build (reset → plan → confirm → execute) ────────────────

    const debugBuild = useCallback(async () => {
        // Reset all backend + frontend state first (same as Reset Demo)
        await Promise.allSettled([
            fetch("/api/backend/conversation/reset", { method: "POST" }),
            fetch("/api/backend/build/reset", { method: "POST" }),
        ]);
        setChats([]);
        questionInfoRef.current = {};

        const chatId = generateId();
        const infoMsg: Message = {
            id: generateId(),
            role: "ai",
            content: "Debug mode \u2014 skipping interview, generating plan\u2026",
            timestamp: new Date(),
        };

        const newChat: Chat = {
            id: chatId,
            title: "Debug Build",
            messages: [infoMsg],
            createdAt: new Date(),
            sessionId: null,
            buildId: null,
            phase: "planning",
            repoUrl: null,
            repoDir: null,
            costEstimate: null,
            buildIteration: 0,
            prdProgress: null,
        };

        setChats([newChat]);
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

            // Poll build status (handles planning_complete → confirming transition)
            pollBuildStatus(chatId, data.build_id);
            pollPrdProgress(chatId, data.build_id);
        } catch {
            addMessage(setChats, chatId, "ai", "Failed to start debug build.");
            setChats((prev) =>
                prev.map((c) =>
                    c.id === chatId ? { ...c, phase: "done" } : c
                )
            );
        }
    }, [pollBuildStatus, pollPrdProgress]);

    // ── Change Estimate Model ─────────────────────────────────────

    const changeEstimateModel = useCallback(
        (chatId: string, model: string) => {
            const chat = chatsRef.current.find((c) => c.id === chatId);
            if (!chat || chat.phase !== "confirming") return;

            if (chat.buildId) {
                setEstimateLoading(true);
                fetch(`/api/backend/build/${chat.buildId}/estimate`, {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ model }),
                })
                    .then((res) => res.ok ? res.json() : null)
                    .then((estimate) => {
                        if (estimate) {
                            setChats((prev) =>
                                prev.map((c) =>
                                    c.id === chatId ? { ...c, costEstimate: estimate } : c
                                )
                            );
                        }
                    })
                    .finally(() => setEstimateLoading(false));
            } else if (chat.sessionId) {
                fetchEstimate(chatId, chat.sessionId, model);
            }
        },
        [fetchEstimate],
    );

    // ── Confirm / Decline Build ─────────────────────────────────────

    const confirmBuild = useCallback(
        async (chatId: string) => {
            const chat = chatsRef.current.find((c) => c.id === chatId);
            if (!chat || !chat.buildId) return;

            const selectedModel = chat.costEstimate?.model ?? "opus";
            addMessage(setChats, chatId, "ai", `Starting the build with ${selectedModel}\u2026`);
            setChats((prev) =>
                prev.map((c) =>
                    c.id === chatId ? { ...c, phase: "building" } : c
                )
            );

            try {
                await fetch(`/api/backend/build/${chat.buildId}/confirm`, {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ model: selectedModel }),
                });
            } catch {
                addMessage(setChats, chatId, "ai", "Failed to confirm build.");
            }
        },
        [],
    );

    const declineBuild = useCallback(
        (chatId: string) => {
            addMessage(setChats, chatId, "ai", "Build cancelled. You can continue the conversation or start a new project.");
            setChats((prev) =>
                prev.map((c) =>
                    c.id === chatId
                        ? { ...c, phase: "conversation", costEstimate: null }
                        : c
                )
            );
        },
        [],
    );

    // ── Reset All (demo cleanup) ──────────────────────────────────

    const resetAll = useCallback(async () => {
        await Promise.allSettled([
            fetch("/api/backend/conversation/reset", { method: "POST" }),
            fetch("/api/backend/build/reset", { method: "POST" }),
        ]);
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
                estimateLoading,
                createChat,
                sendMessage,
                changeEstimateModel,
                confirmBuild,
                declineBuild,
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
