"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import {
    motion,
    useMotionValue,
    useSpring,
    useTransform,
    AnimatePresence,
} from "framer-motion";
import {
    ArrowLeft,
    Bot,
    Send,
    Zap,
    MessageCircle,
    FileText,
    Paperclip,
    X,
    ExternalLink,
    Plus,
    Clock,
    Trash2,
} from "lucide-react";
import Link from "next/link";
import { cn } from "@/lib/utils";
import { useAuth, UserButton, SignOutButton } from "@clerk/nextjs";
import { useQuery, useMutation } from "convex/react";
import { api } from "../../../convex/_generated/api";
import type { Id } from "../../../convex/_generated/dataModel";

const API_BASE = process.env.NEXT_PUBLIC_API_URL
  ? `${process.env.NEXT_PUBLIC_API_URL}/api/v1`
  : "http://localhost:8000/api/v1";

/* ═══════════════════════════════════════════════════════════
   MAGNETIC 3D WRAPPER
   ═══════════════════════════════════════════════════════════ */
function Magnetic3D({
    children,
    className,
    depth = 30,
}: {
    children: React.ReactNode;
    className?: string;
    depth?: number;
}) {
    const ref = useRef<HTMLDivElement>(null);
    const x = useMotionValue(0);
    const y = useMotionValue(0);
    const mx = useSpring(x, { stiffness: 150, damping: 15, mass: 0.1 });
    const my = useSpring(y, { stiffness: 150, damping: 15, mass: 0.1 });
    const rotateX = useTransform(my, [-0.5, 0.5], ["10deg", "-10deg"]);
    const rotateY = useTransform(mx, [-0.5, 0.5], ["-10deg", "10deg"]);

    const handleMouseMove = (e: React.MouseEvent<HTMLDivElement>) => {
        if (!ref.current) return;
        const rect = ref.current.getBoundingClientRect();
        x.set((e.clientX - rect.left) / rect.width - 0.5);
        y.set((e.clientY - rect.top) / rect.height - 0.5);
    };

    return (
        <motion.div
            ref={ref}
            onMouseMove={handleMouseMove}
            onMouseLeave={() => {
                x.set(0);
                y.set(0);
            }}
            style={{ rotateX, rotateY, transformStyle: "preserve-3d" }}
            className={className}
        >
            <div style={{ transform: `translateZ(${depth}px)` }}>{children}</div>
        </motion.div>
    );
}

/* ═══════════════════════════════════════════════════════════
   PULSE LOADER
   ═══════════════════════════════════════════════════════════ */
function PulseLoader() {
    return (
        <div className="relative flex items-center justify-center w-12 h-12">
            <div
                className="absolute inset-0 rounded-full border border-accent/30 animate-ping"
                style={{ animationDuration: "3s" }}
            />
            <div
                className="absolute inset-2 rounded-full border border-accent/50 animate-ping"
                style={{ animationDuration: "2s", animationDelay: "0.4s" }}
            />
            <div className="w-4 h-4 rounded-full bg-accent glow-accent" />
        </div>
    );
}

/* ═══════════════════════════════════════════════════════════
   TYPES
   ═══════════════════════════════════════════════════════════ */
interface Source {
    doc_id: string;
    page_num: number;
    filename: string;
}

interface ChatMessage {
    id?: number;
    role: "user" | "assistant";
    content: string;
    sources?: Source[];
    confidence?: number;
    queryType?: string;
    queryId?: string;
    latencyMs?: number;
}

interface Conversation {
    id: string;
    title: string;
    created_at: string;
    message_count?: number;
}

/* ═══════════════════════════════════════════════════════════
   CHAT PAGE
   ═══════════════════════════════════════════════════════════ */
export default function ChatPage() {
    const { getToken, userId: clerkId } = useAuth();

    /* ─── Convex hooks for conversations + messages ─── */
    const convexConversations = useQuery(api.conversations.listConversations, clerkId ? { clerkId } : "skip");
    const createConvMutation = useMutation(api.conversations.createConversation);
    const deleteConvMutation = useMutation(api.conversations.deleteConversation);
    const sendMessageMutation = useMutation(api.messages.sendMessage);
    const saveAgentResponseMutation = useMutation(api.messages.saveAgentResponse);

    /* ─── Auth-aware fetch wrapper (for FastAPI calls only) ─── */
    const authFetch = useCallback(
        async (url: string, options: RequestInit = {}) => {
            const token = await getToken();
            const headers = new Headers(options.headers);
            if (token) {
                headers.set("Authorization", `Bearer ${token}`);
            }
            return fetch(url, { ...options, headers });
        },
        [getToken]
    );

    const [localMessages, setLocalMessages] = useState<ChatMessage[]>([]);
    const [inputValue, setInputValue] = useState("");
    const [isThinking, setIsThinking] = useState(false);
    const [sidebarOpen, setSidebarOpen] = useState(true);
    const [activeConvId, setActiveConvId] = useState<string | null>(null);
    const [threadId, setThreadId] = useState(
        () => `thread_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`
    );
    const [uploadingFile, setUploadingFile] = useState<string | null>(null);
    const [uploadProgress, setUploadProgress] = useState<string | null>(null);
    const endOfMessagesRef = useRef<HTMLDivElement>(null);
    const fileInputRef = useRef<HTMLInputElement>(null);

    /* ─── Convex messages for active conversation (real-time) ─── */
    const convexMessages = useQuery(
        api.messages.listMessages,
        activeConvId ? { conversationId: activeConvId as Id<"conversations"> } : "skip"
    );

    /* ─── Merge Convex messages with local optimistic messages ─── */
    const messages: ChatMessage[] = activeConvId && convexMessages
        ? convexMessages.map((m) => ({
            role: m.role as "user" | "assistant",
            content: m.content,
            sources: m.sources as Source[] | undefined,
            confidence: m.confidence,
            latencyMs: m.latencyMs,
            queryType: m.queryType,
        }))
        : localMessages;

    useEffect(() => {
        endOfMessagesRef.current?.scrollIntoView({ behavior: "smooth" });
    }, [messages, isThinking]);

    /* ─── Sidebar conversations from Convex (real-time) ─── */
    const conversations: Conversation[] = (convexConversations || []).map((c) => ({
        id: c._id,
        title: c.title,
        created_at: new Date(c.createdAt).toISOString(),
    }));

    /* ─── Create new conversation via Convex ─── */
    const createConversation = useCallback(
        async (title: string): Promise<string | null> => {
            if (!clerkId) return null;
            try {
                const convId = await createConvMutation({ clerkId, title });
                return convId;
            } catch {
                return null;
            }
        },
        [clerkId, createConvMutation]
    );

    /* ─── Select conversation ─── */
    const loadConversation = useCallback((convId: string) => {
        setActiveConvId(convId);
        setThreadId(convId);
        setLocalMessages([]);
    }, []);

    /* ─── Delete conversation via Convex ─── */
    const deleteConversation = useCallback(
        async (convId: string) => {
            try {
                await deleteConvMutation({ conversationId: convId as Id<"conversations"> });
                if (activeConvId === convId) {
                    setLocalMessages([]);
                    setActiveConvId(null);
                }
            } catch {
                /* Silently fail */
            }
        },
        [activeConvId, deleteConvMutation]
    );

    /* ─── New chat ─── */
    const startNewChat = useCallback(() => {
        setLocalMessages([]);
        setActiveConvId(null);
        setThreadId(
            `thread_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`
        );
    }, []);

    /* ─── Send Query: Convex for messages + FastAPI for LLM pipeline ─── */
    const handleSend = useCallback(
        async (e?: React.FormEvent) => {
            e?.preventDefault();
            const question = inputValue.trim();
            if (!question || isThinking) return;

            /* Optimistic local message */
            setLocalMessages((prev) => [...prev, { role: "user", content: question }]);
            setInputValue("");
            setIsThinking(true);

            /* Create conversation in Convex if none exists */
            let convId = activeConvId;
            if (!convId) {
                const title =
                    question.length > 50 ? question.slice(0, 50) + "..." : question;
                convId = await createConversation(title);
                if (convId) {
                    setActiveConvId(convId);
                    setThreadId(convId);
                }
            }

            /* Save user message to Convex */
            if (convId) {
                try {
                    await sendMessageMutation({
                        conversationId: convId as Id<"conversations">,
                        content: question,
                    });
                } catch { /* Convex save failed, continue anyway */ }
            }

            try {
                const res = await authFetch(`${API_BASE}/pageindex/query`, {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({
                        question,
                        thread_id: convId || threadId,
                        user_id: "frontend_user",
                    }),
                });

                if (!res.ok) {
                    const err = await res
                        .json()
                        .catch(() => ({ detail: "Unknown error" }));
                    throw new Error(err.detail || `HTTP ${res.status}`);
                }

                const data = await res.json();
                const assistantMsg: ChatMessage = {
                    role: "assistant",
                    content: data.answer || "No answer generated.",
                    sources: data.sources || [],
                    confidence: data.confidence || 0,
                    queryType: data.query_type || "standard",
                    queryId: data.query_id,
                    latencyMs: data.latency_ms,
                };

                setLocalMessages((prev) => [...prev, assistantMsg]);

                /* Save assistant response to Convex */
                if (convId) {
                    try {
                        await saveAgentResponseMutation({
                            conversationId: convId as Id<"conversations">,
                            content: assistantMsg.content,
                            sources: assistantMsg.sources,
                            confidence: assistantMsg.confidence,
                            latencyMs: assistantMsg.latencyMs,
                            queryType: assistantMsg.queryType,
                        });
                    } catch { /* Convex save failed, local state still has the message */ }
                }
            } catch (err) {
                const errorMessage =
                    err instanceof Error ? err.message : "An unexpected error occurred";
                const errorMsg: ChatMessage = {
                    role: "assistant",
                    content: `Error: ${errorMessage}. Please check that the backend server is running on port 8000.`,
                };
                setLocalMessages((prev) => [...prev, errorMsg]);
            } finally {
                setIsThinking(false);
            }
        },
        [
            inputValue,
            isThinking,
            threadId,
            activeConvId,
            createConversation,
            sendMessageMutation,
            saveAgentResponseMutation,
            authFetch,
        ]
    );

    /* ─── File Upload ─── */
    const handleFileUpload = useCallback(
        async (file: File) => {
            if (!file.name.toLowerCase().endsWith(".pdf")) {
                setUploadProgress("Only PDF files are supported.");
                setTimeout(() => setUploadProgress(null), 3000);
                return;
            }

            setUploadingFile(file.name);
            setUploadProgress("Uploading...");

            try {
                const formData = new FormData();
                formData.append("file", file);

                const res = await authFetch(`${API_BASE}/pageindex/ingest`, {
                    method: "POST",
                    body: formData,
                });

                if (!res.ok) {
                    const err = await res
                        .json()
                        .catch(() => ({ detail: "Upload failed" }));
                    throw new Error(err.detail || `HTTP ${res.status}`);
                }

                const data = await res.json();
                setUploadProgress(
                    `Indexed "${data.filename}" — ${data.total_pages} pages, ${data.node_count} nodes`
                );

                const systemMsg: ChatMessage = {
                    role: "assistant",
                    content: `Successfully indexed **${data.filename}**\n\n- **Pages**: ${data.total_pages}\n- **Tree nodes**: ${data.node_count}\n- **Tree depth**: ${data.tree_depth}\n\nYou can now ask questions about this document.`,
                };
                setLocalMessages((prev) => [...prev, systemMsg]);

                /* Attach document to conversation via Convex */
                let convId = activeConvId;
                if (!convId) {
                    convId = await createConversation(`Uploaded: ${data.filename}`);
                    if (convId) {
                        setActiveConvId(convId);
                        setThreadId(convId);
                    }
                }
                if (convId) {
                    try {
                        await saveAgentResponseMutation({
                            conversationId: convId as Id<"conversations">,
                            content: systemMsg.content,
                        });
                    } catch { /* Convex save failed */ }
                }

                setTimeout(() => {
                    setUploadProgress(null);
                    setUploadingFile(null);
                }, 4000);
            } catch (err) {
                const errorMessage =
                    err instanceof Error ? err.message : "Upload failed";
                setUploadProgress(`Error: ${errorMessage}`);
                setTimeout(() => {
                    setUploadProgress(null);
                    setUploadingFile(null);
                }, 5000);
            }
        },
        [activeConvId, createConversation, saveAgentResponseMutation, authFetch]
    );

    return (
        <div className="flex h-screen w-full relative overflow-hidden text-white font-sans">
            {/* ═══ CONVERSATION SIDEBAR ═══ */}
            <AnimatePresence>
                {sidebarOpen && (
                    <motion.aside
                        initial={{ x: -300, opacity: 0 }}
                        animate={{ x: 0, opacity: 1 }}
                        exit={{ x: -300, opacity: 0 }}
                        transition={{ type: "spring", stiffness: 300, damping: 30 }}
                        className="w-72 h-full border-r border-white/5 bg-black/60 backdrop-blur-xl flex flex-col z-40 shrink-0"
                    >
                        <div className="p-4 border-b border-white/5">
                            <button
                                onClick={startNewChat}
                                className="w-full flex items-center gap-2 px-4 py-3 rounded-xl bg-white/5 border border-white/10 text-sm font-medium hover:bg-accent/10 hover:border-accent/30 transition-all"
                            >
                                <Plus size={16} className="text-accent" />
                                New Chat
                            </button>
                        </div>

                        <div className="flex-1 overflow-y-auto scrollbar-hide p-3 space-y-1">
                            <p className="text-xs text-white/30 font-mono uppercase tracking-widest px-3 py-2">
                                Conversations
                            </p>
                            {conversations.length === 0 ? (
                                <p className="text-white/20 text-xs px-3 py-4 text-center">
                                    No conversations yet
                                </p>
                            ) : (
                                conversations.map((conv) => (
                                    <div
                                        key={conv.id}
                                        className={cn(
                                            "w-full text-left px-3 py-3 rounded-xl text-sm transition-colors group flex items-center gap-3",
                                            conv.id === activeConvId
                                                ? "bg-white/10 text-white border border-white/10"
                                                : "text-white/60 hover:text-white hover:bg-white/5"
                                        )}
                                    >
                                        <button
                                            onClick={() => loadConversation(conv.id)}
                                            aria-label={`Select conversation: ${conv.title}`}
                                            className="flex-1 min-w-0 flex items-center gap-3 text-left"
                                        >
                                            <MessageCircle
                                                size={14}
                                                className={cn(
                                                    "shrink-0 transition-colors",
                                                    conv.id === activeConvId
                                                        ? "text-accent"
                                                        : "text-white/20 group-hover:text-accent"
                                                )}
                                            />
                                            <div className="flex-1 min-w-0">
                                                <p className="truncate text-sm">{conv.title}</p>
                                                <p className="text-xs text-white/20 flex items-center gap-1 mt-0.5">
                                                    <Clock size={10} />{" "}
                                                    {new Date(conv.created_at).toLocaleDateString()}
                                                </p>
                                            </div>
                                        </button>
                                        <button
                                            onClick={(e) => {
                                                e.stopPropagation();
                                                deleteConversation(conv.id);
                                            }}
                                            aria-label="Delete conversation"
                                            title="Delete conversation"
                                            className="opacity-0 group-hover:opacity-100 p-1 rounded-lg hover:bg-destructive/20 text-white/30 hover:text-destructive transition-all"
                                        >
                                            <Trash2 size={12} />
                                        </button>
                                    </div>
                                ))
                            )}
                        </div>

                        <div className="p-3 border-t border-white/5">
                            <Link
                                href="/documents"
                                className="flex items-center gap-2 px-3 py-2 rounded-xl text-sm text-white/40 hover:text-white hover:bg-white/5 transition-colors"
                            >
                                <FileText size={14} />
                                Document Vault
                            </Link>
                        </div>
                    </motion.aside>
                )}
            </AnimatePresence>

            {/* ═══ MAIN CHAT AREA ═══ */}
            <div className="flex-1 flex flex-col relative">
                {/* ─── Top Nav ─── */}
                <motion.nav
                    className="h-16 z-30 flex items-center justify-between px-6 border-b border-white/5 bg-black/40 backdrop-blur-xl shrink-0"
                    initial={{ opacity: 0, y: -20 }}
                    animate={{ opacity: 1, y: 0 }}
                >
                    <div className="flex items-center gap-4">
                        <button
                            onClick={() => setSidebarOpen((v) => !v)}
                            aria-label="Toggle sidebar"
                            title="Toggle sidebar"
                            className="w-9 h-9 rounded-lg bg-white/5 border border-white/10 flex items-center justify-center text-white/50 hover:text-white hover:bg-white/10 transition-all"
                        >
                            {sidebarOpen ? (
                                <ArrowLeft size={16} />
                            ) : (
                                <MessageCircle size={16} />
                            )}
                        </button>
                        <div className="flex flex-col">
                            <span className="font-bold text-sm tracking-widest uppercase">
                                FinSight AI
                            </span>
                            <span className="text-xs text-accent font-mono uppercase tracking-widest">
                                {isThinking
                                    ? "■ Analyzing documents..."
                                    : uploadingFile
                                        ? `■ Indexing ${uploadingFile}...`
                                        : "■ System Ready"}
                            </span>
                        </div>
                    </div>

                    <div className="flex items-center gap-3">
                        <Link
                            href="/documents"
                            className="px-4 py-2 rounded-full border border-white/10 text-xs font-bold uppercase tracking-wider hover:bg-white/10 transition-colors"
                        >
                            Document Vault
                        </Link>
                        <Link
                            href="/"
                            className="w-9 h-9 rounded-lg bg-white/5 border border-white/10 flex items-center justify-center text-white/50 hover:text-white hover:bg-white/10 transition-all"
                        >
                            <ArrowLeft size={16} />
                        </Link>
                        <UserButton
                            appearance={{
                                elements: {
                                    avatarBox: "w-8 h-8 border border-white/20",
                                },
                            }}
                        />
                    </div>
                </motion.nav>

                {/* ─── Upload progress banner ─── */}
                <AnimatePresence>
                    {uploadProgress && (
                        <motion.div
                            initial={{ height: 0, opacity: 0 }}
                            animate={{ height: "auto", opacity: 1 }}
                            exit={{ height: 0, opacity: 0 }}
                            className="px-6 py-3 bg-accent/10 border-b border-accent/20 text-accent text-sm font-mono flex items-center gap-3 overflow-hidden"
                        >
                            {uploadingFile && !uploadProgress.startsWith("Error") && (
                                <div className="w-4 h-4 border-2 border-accent border-t-transparent rounded-full animate-spin" />
                            )}
                            {uploadProgress}
                            <button
                                onClick={() => {
                                    setUploadProgress(null);
                                    setUploadingFile(null);
                                }}
                                className="ml-auto text-white/40 hover:text-white"
                            >
                                <X size={14} />
                            </button>
                        </motion.div>
                    )}
                </AnimatePresence>

                {/* ─── Messages area ─── */}
                <div className="flex-1 overflow-y-auto scrollbar-hide">
                    <div className="max-w-3xl mx-auto px-4 py-8">
                        {messages.length === 0 ? (
                            /* ─── Premium Empty State ─── */
                            <motion.div
                                className="flex flex-col items-center justify-center mt-24"
                                initial={{ opacity: 0, scale: 0.95 }}
                                animate={{ opacity: 1, scale: 1 }}
                                transition={{ duration: 0.6 }}
                            >
                                <Magnetic3D depth={40}>
                                    <div className="w-28 h-28 rounded-3xl bg-black/50 border border-white/5 flex items-center justify-center mb-8 shadow-[0_0_80px_rgba(139,154,109,0.08)]">
                                        <PulseLoader />
                                    </div>
                                </Magnetic3D>

                                <h1 className="text-4xl font-bold tracking-tighter mb-3 text-center">
                                    FinSight AI
                                </h1>
                                <p className="text-white/40 text-sm font-light text-center max-w-md mb-14">
                                    Your intelligent finance document companion.
                                    <br />
                                    Attach PDFs and ask questions.
                                </p>

                                <div className="grid grid-cols-1 md:grid-cols-3 gap-3 w-full max-w-2xl">
                                    {[
                                        {
                                            icon: Zap,
                                            text: "What was the total revenue last quarter?",
                                        },
                                        {
                                            icon: MessageCircle,
                                            text: "Summarize the key financial highlights",
                                        },
                                        {
                                            icon: FileText,
                                            text: "Compare year-over-year performance",
                                        },
                                    ].map((sug, i) => (
                                        <Magnetic3D key={i} depth={15} className="w-full">
                                            <button
                                                onClick={() => setInputValue(sug.text)}
                                                className="w-full text-left p-4 rounded-2xl bg-white/[0.03] border border-white/10 hover:bg-white/[0.06] hover:border-accent/30 transition-all group flex items-start gap-3"
                                            >
                                                <sug.icon
                                                    size={16}
                                                    className="text-white/30 group-hover:text-accent transition-colors mt-0.5 shrink-0"
                                                />
                                                <span className="text-xs font-medium text-white/50 group-hover:text-white/80 transition-colors leading-relaxed">
                                                    {sug.text}
                                                </span>
                                            </button>
                                        </Magnetic3D>
                                    ))}
                                </div>
                            </motion.div>
                        ) : (
                            /* ─── Messages ─── */
                            <div className="space-y-6">
                                {messages.map((msg, i) => (
                                    <motion.div
                                        key={i}
                                        className={cn(
                                            "flex w-full",
                                            msg.role === "user" ? "justify-end" : "justify-start"
                                        )}
                                        initial={{ opacity: 0, y: 15 }}
                                        animate={{ opacity: 1, y: 0 }}
                                        transition={{
                                            type: "spring",
                                            stiffness: 200,
                                            damping: 20,
                                        }}
                                    >
                                        <div
                                            className={cn(
                                                "max-w-2xl font-light leading-relaxed text-[14px]",
                                                msg.role === "user"
                                                    ? "bg-white/[0.06] border border-white/15 text-white rounded-2xl rounded-tr-sm px-5 py-4"
                                                    : "relative"
                                            )}
                                        >
                                            {msg.role === "assistant" && (
                                                <div className="flex items-start gap-3">
                                                    <div className="w-7 h-7 rounded-lg bg-accent/10 border border-accent/20 flex items-center justify-center shrink-0 mt-0.5">
                                                        <Bot size={14} className="text-accent" />
                                                    </div>
                                                    <div className="flex-1 min-w-0">
                                                        <div className="bg-black/40 border border-white/10 rounded-2xl rounded-tl-sm px-5 py-4 relative overflow-hidden">
                                                            <div className="absolute top-0 left-0 w-0.5 h-full bg-accent/50" />
                                                            <p className="text-white/85 whitespace-pre-wrap">
                                                                {msg.content}
                                                            </p>
                                                        </div>

                                                        {/* Citation pills + confidence */}
                                                        {(msg.sources?.length ||
                                                            msg.confidence !== undefined) && (
                                                                <div className="flex flex-wrap items-center gap-2 mt-2 px-1">
                                                                    {msg.sources?.map((src, j) => (
                                                                        <Link
                                                                            key={j}
                                                                            href="/documents"
                                                                            className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-accent/8 border border-accent/20 text-accent text-xs font-mono hover:bg-accent/15 transition-colors"
                                                                        >
                                                                            <FileText size={10} />
                                                                            Page {src.page_num}
                                                                            {src.filename && (
                                                                                <span className="text-white/30 ml-1">
                                                                                    ·{" "}
                                                                                    {src.filename
                                                                                        .split(".")[0]
                                                                                        .slice(0, 15)}
                                                                                </span>
                                                                            )}
                                                                            <ExternalLink
                                                                                size={8}
                                                                                className="ml-0.5"
                                                                            />
                                                                        </Link>
                                                                    ))}

                                                                    {msg.confidence !== undefined &&
                                                                        msg.confidence > 0 && (
                                                                            <span
                                                                                className={cn(
                                                                                    "px-3 py-1 rounded-full text-xs font-mono border",
                                                                                    msg.confidence >= 0.7
                                                                                        ? "bg-accent/10 text-accent border-accent/20"
                                                                                        : msg.confidence >= 0.4
                                                                                            ? "bg-yellow-500/10 text-yellow-400 border-yellow-500/20"
                                                                                            : "bg-destructive/10 text-destructive border-destructive/20"
                                                                                )}
                                                                            >
                                                                                {Math.round(msg.confidence * 100)}%
                                                                                confident
                                                                            </span>
                                                                        )}

                                                                    {msg.latencyMs && (
                                                                        <span className="text-white/20 text-xs font-mono">
                                                                            {(msg.latencyMs / 1000).toFixed(1)}s
                                                                        </span>
                                                                    )}
                                                                </div>
                                                            )}
                                                    </div>
                                                </div>
                                            )}

                                            {msg.role === "user" && msg.content}
                                        </div>
                                    </motion.div>
                                ))}

                                {/* Thinking state */}
                                <AnimatePresence>
                                    {isThinking && (
                                        <motion.div
                                            initial={{ opacity: 0, y: 10 }}
                                            animate={{ opacity: 1, y: 0 }}
                                            exit={{ opacity: 0, scale: 0.95 }}
                                            className="flex justify-start w-full"
                                        >
                                            <div className="flex items-start gap-3">
                                                <div className="w-7 h-7 rounded-lg bg-accent/10 border border-accent/20 flex items-center justify-center shrink-0 mt-0.5">
                                                    <Bot size={14} className="text-accent" />
                                                </div>
                                                <div className="bg-black/40 border border-white/10 rounded-2xl rounded-tl-sm px-5 py-4 flex items-center gap-4 relative overflow-hidden">
                                                    <div className="absolute top-0 left-0 w-0.5 h-full bg-accent/30 animate-pulse" />
                                                    <PulseLoader />
                                                    <span className="text-white/40 text-xs font-mono tracking-wider uppercase">
                                                        Analyzing documents...
                                                    </span>
                                                </div>
                                            </div>
                                        </motion.div>
                                    )}
                                </AnimatePresence>

                                <div ref={endOfMessagesRef} className="h-4" />
                            </div>
                        )}
                    </div>
                </div>

                {/* ═══ FLOATING INPUT BAR — LIQUID GLASS ═══ */}
                <div className="px-4 pb-6 pt-2">
                    <div className="max-w-3xl mx-auto">
                        <Magnetic3D depth={15}>
                            <form
                                onSubmit={handleSend}
                                className="liquid-glass flex items-center gap-2 p-2 rounded-2xl focus-within:border-accent/40 focus-within:shadow-[0_0_30px_rgba(139,154,109,0.15)] transition-all"
                            >
                                {/* PDF attachment */}
                                <input
                                    ref={fileInputRef}
                                    type="file"
                                    accept=".pdf"
                                    className="hidden"
                                    aria-label="Upload PDF to chat"
                                    title="Upload PDF"
                                    onChange={(e) => {
                                        const file = e.target.files?.[0];
                                        if (file) handleFileUpload(file);
                                        e.target.value = "";
                                    }}
                                />
                                <button
                                    type="button"
                                    onClick={() => fileInputRef.current?.click()}
                                    className="w-10 h-10 rounded-xl bg-white/5 flex items-center justify-center text-white/30 hover:text-accent hover:bg-accent/10 transition-all shrink-0"
                                    title="Attach PDF"
                                >
                                    <Paperclip size={16} />
                                </button>

                                <input
                                    value={inputValue}
                                    onChange={(e) => setInputValue(e.target.value)}
                                    placeholder="Ask a question about your documents..."
                                    aria-label="Chat input"
                                    title="Chat input"
                                    className="flex-1 bg-transparent border-0 outline-none text-white placeholder:text-white/25 text-sm px-2 font-light"
                                    disabled={isThinking}
                                />

                                <button
                                    type="submit"
                                    disabled={!inputValue.trim() || isThinking}
                                    aria-label="Send message"
                                    title="Send message"
                                    className="w-10 h-10 rounded-xl bg-white flex items-center justify-center text-black hover:bg-accent hover:text-white transition-all disabled:opacity-20 disabled:hover:bg-white disabled:hover:text-black shrink-0"
                                >
                                    <Send size={16} />
                                </button>
                            </form>
                        </Magnetic3D>
                    </div>
                </div>
            </div>
        </div>
    );
}
