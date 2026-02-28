"use client";

import { useEffect, useRef, useState, useCallback } from "react";
import {
    motion,
    useMotionValue,
    useSpring,
    useTransform,
} from "framer-motion";
import gsap from "gsap";
import {
    ArrowLeft,
    FileText,
    CheckCircle2,
    AlertCircle,
    RefreshCw,
    Layers,
    Zap,
    Upload,
    Search,
    X,
} from "lucide-react";
import Link from "next/link";
import { cn } from "@/lib/utils";
import { useAuth, UserButton } from "@clerk/nextjs";
import { useQuery } from "convex/react";
import { api } from "../../../convex/_generated/api";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

/* ─── 3D Magnetic Card ─── */
function MagneticCard({
    children,
    className,
}: {
    children: React.ReactNode;
    className?: string;
}) {
    const ref = useRef<HTMLDivElement>(null);
    const x = useMotionValue(0);
    const y = useMotionValue(0);
    const mx = useSpring(x, { stiffness: 150, damping: 15, mass: 0.1 });
    const my = useSpring(y, { stiffness: 150, damping: 15, mass: 0.1 });
    const rotateX = useTransform(my, [-0.5, 0.5], ["12deg", "-12deg"]);
    const rotateY = useTransform(mx, [-0.5, 0.5], ["-12deg", "12deg"]);

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
            <div style={{ transform: "translateZ(30px)" }}>{children}</div>
        </motion.div>
    );
}

/* ─── Types ─── */
interface DocumentInfo {
    doc_id: string;
    filename: string;
    title: string;
    total_pages: number;
    description: string;
}

export default function DocumentsPage() {
    const { getToken } = useAuth();

    /* ─── Fetch Wrapper ─── */
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

    const [searchQuery, setSearchQuery] = useState("");
    const [documents, setDocuments] = useState<DocumentInfo[]>([]);
    const [loading, setLoading] = useState(true);
    const [uploading, setUploading] = useState(false);
    const [uploadStatus, setUploadStatus] = useState<string | null>(null);
    const fileInputRef = useRef<HTMLInputElement>(null);
    const headerRef = useRef<HTMLDivElement>(null);
    const gridRef = useRef<HTMLDivElement>(null);

    /* ─── Fetch real documents from backend ─── */
    const fetchDocuments = useCallback(async () => {
        try {
            const res = await authFetch(`${API_BASE}/pageindex/documents`);
            if (res.ok) {
                const data: DocumentInfo[] = await res.json();
                setDocuments(data);
            }
        } catch {
            /* Backend might not be running */
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => {
        fetchDocuments();
    }, [fetchDocuments]);

    /* ─── GSAP animations ─── */
    useEffect(() => {
        if (loading) return;

        gsap.fromTo(
            headerRef.current,
            { opacity: 0, y: -40 },
            { opacity: 1, y: 0, duration: 1.2, ease: "power4.out" }
        );

        if (gridRef.current && gridRef.current.children.length > 0) {
            gsap.fromTo(
                gridRef.current.children,
                { opacity: 0, scale: 0.92, y: 40 },
                {
                    opacity: 1,
                    scale: 1,
                    y: 0,
                    duration: 0.8,
                    stagger: 0.08,
                    ease: "power3.out",
                    delay: 0.2,
                }
            );
        }
    }, [loading, documents]);

    /* ─── Filter ─── */
    const filteredDocs = documents.filter(
        (doc) =>
            doc.filename.toLowerCase().includes(searchQuery.toLowerCase()) ||
            doc.title.toLowerCase().includes(searchQuery.toLowerCase())
    );

    /* ─── Total pages ─── */
    const totalPages = documents.reduce((sum, d) => sum + d.total_pages, 0);

    /* ─── Upload handler ─── */
    const handleUpload = useCallback(
        async (file: File) => {
            if (!file.name.toLowerCase().endsWith(".pdf")) {
                setUploadStatus("Only PDF files are supported.");
                setTimeout(() => setUploadStatus(null), 3000);
                return;
            }

            setUploading(true);
            setUploadStatus(`Indexing ${file.name}...`);

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
                setUploadStatus(
                    `Successfully indexed "${data.filename}" — ${data.total_pages} pages, ${data.node_count} nodes`
                );
                // Refresh document list
                await fetchDocuments();

                setTimeout(() => setUploadStatus(null), 5000);
            } catch (err) {
                const msg = err instanceof Error ? err.message : "Upload failed";
                setUploadStatus(`Error: ${msg}`);
                setTimeout(() => setUploadStatus(null), 5000);
            } finally {
                setUploading(false);
            }
        },
        [fetchDocuments]
    );

    return (
        <div className="min-h-screen w-full relative overflow-hidden text-white font-sans pb-40">
            {/* ═══ NAVIGATION ═══ */}
            <motion.nav
                className="fixed top-0 left-0 right-0 h-16 z-50 flex items-center justify-between px-6 md:px-10 glass-panel border-b border-white/5"
                initial={{ opacity: 0, y: -20 }}
                animate={{ opacity: 1, y: 0 }}
            >
                <div className="flex items-center gap-4">
                    <Link
                        href="/chat"
                        className="text-white/50 hover:text-white transition-colors group p-2 rounded-lg hover:bg-white/5"
                    >
                        <ArrowLeft
                            size={18}
                            className="group-hover:-translate-x-1 transition-transform"
                        />
                    </Link>
                    <span className="font-bold text-sm tracking-widest uppercase">
                        Document Vault
                    </span>
                </div>

                <div className="flex items-center gap-3">
                    <input
                        ref={fileInputRef}
                        type="file"
                        accept=".pdf"
                        className="hidden"
                        aria-label="Upload PDF document"
                        title="Upload PDF"
                        onChange={(e) => {
                            const file = e.target.files?.[0];
                            if (file) handleUpload(file);
                            e.target.value = "";
                        }}
                    />
                    <button
                        onClick={() => fileInputRef.current?.click()}
                        disabled={uploading}
                        className="flex items-center gap-2 px-5 py-2 rounded-full bg-white text-black text-xs font-bold uppercase tracking-wider hover:bg-accent hover:text-white transition-all disabled:opacity-50"
                    >
                        <Upload size={14} /> Upload PDF
                    </button>
                    <UserButton
                        appearance={{
                            elements: {
                                avatarBox: "w-8 h-8 border border-white/20",
                            },
                        }}
                    />
                </div>
            </motion.nav>

            {/* ═══ Upload Status Banner ═══ */}
            {uploadStatus && (
                <motion.div
                    initial={{ opacity: 0, height: 0 }}
                    animate={{ opacity: 1, height: "auto" }}
                    className="fixed top-16 left-0 right-0 z-40 px-6 py-3 bg-accent/10 border-b border-accent/20 text-accent text-sm font-mono flex items-center gap-3"
                >
                    {uploading && (
                        <div className="w-4 h-4 border-2 border-accent border-t-transparent rounded-full animate-spin" />
                    )}
                    {uploadStatus}
                    <button
                        onClick={() => setUploadStatus(null)}
                        aria-label="Close upload status banner"
                        title="Close upload status"
                        className="ml-auto text-white/40 hover:text-white"
                    >
                        <X size={14} />
                    </button>
                </motion.div>
            )}

            {/* ═══ HEADER STATS ═══ */}
            <div
                ref={headerRef}
                className="pt-28 px-6 md:px-10 max-w-7xl mx-auto flex flex-col md:flex-row gap-8 items-end justify-between mb-14"
            >
                <div>
                    <h1 className="text-4xl md:text-6xl font-bold tracking-tighter mb-3">
                        YOUR
                        <br />
                        <span className="text-transparent bg-clip-text bg-gradient-to-r from-accent to-white opacity-90">
                            DOCUMENTS
                        </span>
                    </h1>
                    <p className="text-white/40 max-w-md font-light text-sm">
                        Documents indexed through FinSight. Upload PDFs to add more to your
                        corpus.
                    </p>
                </div>

                <div className="flex gap-4">
                    <div className="glass-panel p-5 rounded-2xl">
                        <span className="text-accent text-xs font-mono tracking-widest uppercase mb-1 block">
                            Documents
                        </span>
                        <div className="text-3xl font-bold">{documents.length}</div>
                    </div>
                    <div className="glass-panel p-5 rounded-2xl">
                        <span className="text-white/40 text-xs font-mono tracking-widest uppercase mb-1 block">
                            Total Pages
                        </span>
                        <div className="text-3xl font-bold text-white/60">
                            {totalPages.toLocaleString()}
                        </div>
                    </div>
                </div>
            </div>

            {/* ═══ SEARCH BAR ═══ */}
            <div className="px-6 md:px-10 max-w-7xl mx-auto mb-10">
                <div className="w-full max-w-md">
                    <div className="relative group">
                        <div className="absolute inset-0 bg-accent/10 blur-xl rounded-full opacity-0 group-focus-within:opacity-100 transition-opacity duration-500" />
                        <div className="relative flex items-center bg-black/50 border border-white/10 p-2 rounded-full backdrop-blur-xl focus-within:border-accent/30 transition-colors">
                            <div className="w-9 h-9 flex items-center justify-center">
                                <Search size={16} className="text-white/40" />
                            </div>
                            <input
                                type="text"
                                placeholder="Search documents..."
                                aria-label="Search documents"
                                title="Search documents"
                                value={searchQuery}
                                onChange={(e) => setSearchQuery(e.target.value)}
                                className="bg-transparent border-0 outline-none text-white w-full px-2 text-sm placeholder:text-white/25"
                            />
                        </div>
                    </div>
                </div>
            </div>

            {/* ═══ DOCUMENT GRID ═══ */}
            <div className="px-6 md:px-10 max-w-7xl mx-auto">
                {loading ? (
                    <div className="flex items-center justify-center py-20">
                        <div className="w-8 h-8 border-2 border-accent border-t-transparent rounded-full animate-spin" />
                        <span className="ml-4 text-white/40 text-sm font-mono">
                            Loading documents...
                        </span>
                    </div>
                ) : filteredDocs.length === 0 ? (
                    <div className="text-center py-20">
                        <FileText
                            size={48}
                            className="text-white/10 mx-auto mb-4"
                        />
                        <p className="text-white/30 text-sm">
                            {documents.length === 0
                                ? "No documents indexed yet. Upload a PDF to get started."
                                : "No documents match your search."}
                        </p>
                    </div>
                ) : (
                    <div
                        ref={gridRef}
                        className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5"
                    >
                        {filteredDocs.map((doc) => (
                            <MagneticCard key={doc.doc_id}>
                                <div className="relative group p-6 rounded-[1.5rem] border border-white/10 bg-black/40 backdrop-blur-md overflow-hidden hover:bg-black/60 transition-colors cursor-pointer h-full flex flex-col justify-between">
                                    {/* Background glow */}
                                    <div className="absolute -top-16 -right-16 w-32 h-32 rounded-full blur-[50px] bg-accent opacity-0 group-hover:opacity-10 transition-opacity duration-700" />

                                    <div>
                                        <div className="flex justify-between items-start mb-5">
                                            <div className="w-11 h-11 rounded-xl bg-white/5 flex items-center justify-center border border-white/10 group-hover:scale-110 transition-transform">
                                                <FileText size={18} className="text-white/60" />
                                            </div>
                                            <div className="px-3 py-1 rounded-full text-xs font-mono uppercase tracking-widest flex items-center gap-1.5 border bg-accent/10 text-accent border-accent/20">
                                                <CheckCircle2 size={10} />
                                                indexed
                                            </div>
                                        </div>

                                        <h3
                                            className="text-sm font-medium text-white/85 mb-1.5 line-clamp-2"
                                            title={doc.filename}
                                        >
                                            {doc.filename}
                                        </h3>
                                        {doc.title && doc.title !== doc.filename && (
                                            <p className="text-xs text-white/30 mb-2 line-clamp-1">
                                                {doc.title}
                                            </p>
                                        )}
                                        <p className="text-xs font-light text-white/40">
                                            {doc.total_pages} pages
                                        </p>
                                    </div>
                                </div>
                            </MagneticCard>
                        ))}
                    </div>
                )}
            </div>

            {/* ═══ HOW INDEXING WORKS ═══ */}
            <div className="pt-20 pb-10 px-6 md:px-10 max-w-5xl mx-auto border-t border-white/5 mt-20 text-center">
                <h3 className="text-xl font-bold tracking-tight text-white mb-10">
                    How FinSight Indexes Your Documents
                </h3>
                <div className="flex flex-col md:flex-row items-center justify-between gap-5 relative">
                    {/* Connecting line */}
                    <div className="hidden md:block absolute top-10 left-[10%] right-[10%] h-px bg-gradient-to-r from-transparent via-white/10 to-transparent -z-10" />

                    {[
                        {
                            icon: FileText,
                            title: "Validate",
                            desc: "PDF format & size check",
                        },
                        {
                            icon: Layers,
                            title: "Extract",
                            desc: "Pages, metadata & tables",
                        },
                        {
                            icon: Zap,
                            title: "Build Tree",
                            desc: "AI-generated topic index",
                        },
                        {
                            icon: CheckCircle2,
                            title: "Ready",
                            desc: "Searchable & queryable",
                        },
                    ].map((step, i) => (
                        <div
                            key={i}
                            className="flex flex-col items-center bg-black/40 p-5 rounded-2xl border border-white/5 backdrop-blur-xl w-full md:w-1/4 group hover:bg-white/5 transition-colors"
                        >
                            <div className="w-12 h-12 rounded-full bg-white/5 border border-white/10 flex items-center justify-center mb-4 group-hover:scale-110 group-hover:bg-accent/10 transition-all duration-300">
                                <step.icon
                                    size={20}
                                    className="text-white/40 group-hover:text-accent transition-colors"
                                />
                            </div>
                            <span className="text-white font-medium text-sm mb-1">
                                {step.title}
                            </span>
                            <p className="text-white/35 text-xs font-light text-center">
                                {step.desc}
                            </p>
                        </div>
                    ))}
                </div>
            </div>
        </div>
    );
}
