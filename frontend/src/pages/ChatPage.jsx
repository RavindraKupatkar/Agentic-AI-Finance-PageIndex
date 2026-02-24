import { useState, useRef, useEffect, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
    Send, Bot, User, FileText, Loader2, Sparkles, Zap,
    ArrowRight, MessageCircle, Paperclip, X, CheckCircle,
    ExternalLink, ChevronDown, ChevronUp,
} from 'lucide-react';
import {
    queryDocuments,
    ingestPDF,
    getPageContent,
    createConversation,
    getConversation,
    addMessage,
    attachDocument,
} from '../api/client';
import { useAppContext } from '../components/layout/AppShell';
import '../styles/chat.css';

const messageVariants = {
    initial: { opacity: 0, y: 16, scale: 0.97 },
    animate: { opacity: 1, y: 0, scale: 1, transition: { duration: 0.4, ease: [0.4, 0, 0.2, 1] } },
    exit: { opacity: 0, transition: { duration: 0.15 } },
};

const SUGGESTIONS = [
    { icon: Zap, text: "What was the total revenue last quarter?" },
    { icon: MessageCircle, text: "Summarize the key financial highlights" },
    { icon: FileText, text: "Compare year-over-year performance" },
];

export default function ChatPage() {
    const { activeConversationId, setActiveConversationId } = useAppContext();
    const [messages, setMessages] = useState([]);
    const [input, setInput] = useState('');
    const [loading, setLoading] = useState(false);
    const [attachedFiles, setAttachedFiles] = useState([]);
    const [ingesting, setIngesting] = useState(false);
    const [ingestStep, setIngestStep] = useState('');
    const [expandedPage, setExpandedPage] = useState(null);
    const [pageContent, setPageContent] = useState({});
    const [loadingPage, setLoadingPage] = useState(null);
    const [conversationId, setConversationId] = useState(activeConversationId);
    const messagesEndRef = useRef(null);
    const fileInputRef = useRef(null);
    const textareaRef = useRef(null);

    // Load conversation when activeConversationId changes
    useEffect(() => {
        if (activeConversationId && activeConversationId !== conversationId) {
            loadConversation(activeConversationId);
        }
    }, [activeConversationId]);

    const loadConversation = async (convId) => {
        try {
            const conv = await getConversation(convId);
            if (conv?.messages) {
                setMessages(conv.messages.map(m => ({
                    role: m.role,
                    content: m.content,
                    sources: m.sources,
                    confidence: m.confidence,
                    latency_ms: m.latency_ms,
                    timestamp: m.created_at,
                })));
                setConversationId(convId);
            }
        } catch {
            // silent
        }
    };

    useEffect(() => {
        messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }, [messages]);

    const handleFileAttach = (e) => {
        const files = Array.from(e.target.files).filter(f => f.name.endsWith('.pdf'));
        setAttachedFiles(prev => [...prev, ...files]);
        e.target.value = '';
    };

    const removeFile = (idx) => {
        setAttachedFiles(prev => prev.filter((_, i) => i !== idx));
    };

    const handleCitationClick = async (docId, pageNum) => {
        const key = `${docId}-${pageNum}`;
        if (expandedPage === key) {
            setExpandedPage(null);
            return;
        }

        if (pageContent[key]) {
            setExpandedPage(key);
            return;
        }

        try {
            setLoadingPage(key);
            const data = await getPageContent(docId, pageNum);
            setPageContent(prev => ({ ...prev, [key]: data.content }));
            setExpandedPage(key);
        } catch {
            setPageContent(prev => ({ ...prev, [key]: 'Failed to load page content.' }));
            setExpandedPage(key);
        } finally {
            setLoadingPage(null);
        }
    };

    const handleSend = async (overrideText) => {
        const text = overrideText || input.trim();
        if ((!text && attachedFiles.length === 0) || loading) return;

        // Ensure we have a conversation
        let convId = conversationId;
        if (!convId) {
            try {
                const conv = await createConversation(text.substring(0, 80));
                convId = conv.id;
                setConversationId(convId);
                setActiveConversationId(convId);
            } catch {
                // continue without persistence
            }
        }

        // Add user message
        const userMsg = {
            role: 'user',
            content: text || `Attached ${attachedFiles.length} document(s)`,
            timestamp: new Date().toISOString(),
            attachedFiles: attachedFiles.map(f => f.name),
        };
        setMessages(prev => [...prev, userMsg]);
        setInput('');

        // Save user message
        if (convId) {
            try { await addMessage(convId, 'user', userMsg.content); } catch { }
        }

        // Step 1: Ingest attached files (if any)
        const ingestedDocs = [];
        if (attachedFiles.length > 0) {
            setIngesting(true);
            for (const file of attachedFiles) {
                try {
                    setIngestStep(`Uploading ${file.name}...`);
                    const result = await ingestPDF(file);
                    ingestedDocs.push(result);

                    // Attach document to conversation
                    if (convId) {
                        try {
                            await attachDocument(convId, result.doc_id, result.filename, result.total_pages);
                        } catch { }
                    }
                } catch (err) {
                    setMessages(prev => [...prev, {
                        role: 'assistant',
                        content: `Failed to ingest ${file.name}: ${err.message || 'Unknown error'}`,
                        error: true,
                        timestamp: new Date().toISOString(),
                    }]);
                }
            }
            setIngesting(false);
            setIngestStep('');
            setAttachedFiles([]);

            if (ingestedDocs.length > 0) {
                const ingestMsg = {
                    role: 'assistant',
                    content: `✅ Successfully indexed ${ingestedDocs.length} document(s):\n${ingestedDocs.map(d => `• **${d.filename}** — ${d.total_pages} pages, ${d.node_count} tree nodes`).join('\n')}`,
                    timestamp: new Date().toISOString(),
                };
                setMessages(prev => [...prev, ingestMsg]);
                if (convId) {
                    try { await addMessage(convId, 'assistant', ingestMsg.content); } catch { }
                }
            }
        }

        // Step 2: Query (if there's text)
        if (text) {
            setLoading(true);
            try {
                const response = await queryDocuments(text, convId || 'default');
                const assistantMsg = {
                    role: 'assistant',
                    content: response.answer,
                    sources: response.sources,
                    confidence: response.confidence,
                    latency_ms: response.latency_ms,
                    timestamp: new Date().toISOString(),
                };
                setMessages(prev => [...prev, assistantMsg]);

                // Save assistant message
                if (convId) {
                    try {
                        await addMessage(
                            convId, 'assistant', response.answer,
                            response.sources, response.confidence, response.latency_ms
                        );
                    } catch { }
                }
            } catch (err) {
                const errorMsg = {
                    role: 'assistant',
                    content: err.response?.data?.detail || err.message || 'Something went wrong.',
                    error: true,
                    timestamp: new Date().toISOString(),
                };
                setMessages(prev => [...prev, errorMsg]);
            } finally {
                setLoading(false);
            }
        }
    };

    const handleKeyDown = (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            handleSend();
        }
    };

    const renderMessage = (msg, idx) => (
        <motion.div
            key={idx}
            variants={messageVariants}
            initial="initial"
            animate="animate"
            exit="exit"
            className={`chat-message ${msg.role}`}
        >
            <div className="chat-message-avatar">
                {msg.role === 'user' ? (
                    <div className="avatar-user"><User size={16} /></div>
                ) : (
                    <div className={`avatar-ai ${loading && idx === messages.length - 1 ? 'thinking' : ''}`}>
                        <Bot size={16} />
                    </div>
                )}
            </div>
            <div className="chat-message-body">
                <div className="chat-message-header">
                    <span className="chat-message-name">
                        {msg.role === 'user' ? 'You' : 'FinSight AI'}
                    </span>
                    <span className="chat-message-time">
                        {new Date(msg.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                    </span>
                </div>
                <div className={`chat-bubble ${msg.role} ${msg.error ? 'error' : ''}`}>
                    {renderContent(msg.content)}
                </div>

                {/* Attached files */}
                {msg.attachedFiles && msg.attachedFiles.length > 0 && (
                    <div className="chat-attached-files">
                        {msg.attachedFiles.map((f, i) => (
                            <span key={i} className="chat-attached-pill">
                                <Paperclip size={12} />{f}
                            </span>
                        ))}
                    </div>
                )}

                {/* Clickable Sources */}
                {msg.sources && msg.sources.length > 0 && (
                    <div className="chat-sources">
                        <span className="chat-sources-label">Sources:</span>
                        {msg.sources.map((s, i) => {
                            const key = `${s.doc_id}-${s.page_num}`;
                            return (
                                <div key={i} className="chat-source-wrapper">
                                    <button
                                        className={`chat-source-badge clickable ${expandedPage === key ? 'active' : ''}`}
                                        onClick={() => handleCitationClick(s.doc_id, s.page_num)}
                                    >
                                        <FileText size={12} />
                                        <span>{s.filename}</span>
                                        <span className="chat-source-page">p.{s.page_num}</span>
                                        {loadingPage === key ? (
                                            <Loader2 size={10} className="spin" />
                                        ) : expandedPage === key ? (
                                            <ChevronUp size={10} />
                                        ) : (
                                            <ChevronDown size={10} />
                                        )}
                                    </button>
                                    {expandedPage === key && pageContent[key] && (
                                        <motion.div
                                            className="chat-source-content"
                                            initial={{ opacity: 0, height: 0 }}
                                            animate={{ opacity: 1, height: 'auto' }}
                                            exit={{ opacity: 0, height: 0 }}
                                        >
                                            <div className="chat-source-content-header">
                                                <span>{s.filename} — Page {s.page_num}</span>
                                            </div>
                                            <pre className="chat-source-content-text">{pageContent[key]}</pre>
                                        </motion.div>
                                    )}
                                </div>
                            );
                        })}
                    </div>
                )}

                {/* Meta */}
                {msg.latency_ms && (
                    <div className="chat-meta">
                        <span className="chat-meta-latency">{Math.round(msg.latency_ms)}ms</span>
                        {msg.confidence && (
                            <span className="chat-meta-confidence">{Math.round(msg.confidence * 100)}% confident</span>
                        )}
                    </div>
                )}
            </div>
        </motion.div>
    );

    const renderContent = (text) => {
        if (!text) return null;
        const parts = text.split(/(\*\*[^*]+\*\*)/g);
        return (
            <p>
                {parts.map((part, i) =>
                    part.startsWith('**') && part.endsWith('**')
                        ? <strong key={i}>{part.slice(2, -2)}</strong>
                        : part.split('\n').map((line, j) => (
                            <span key={`${i}-${j}`}>{line}{j < part.split('\n').length - 1 && <br />}</span>
                        ))
                )}
            </p>
        );
    };

    const isEmpty = messages.length === 0;

    return (
        <div className="chat-page">
            <div className="chat-messages">
                <AnimatePresence mode="popLayout">
                    {isEmpty ? (
                        <motion.div
                            key="empty"
                            className="chat-empty"
                            initial={{ opacity: 0 }}
                            animate={{ opacity: 1 }}
                            exit={{ opacity: 0 }}
                        >
                            <div className="chat-empty-logo">
                                <div className="chat-empty-logo-orb">
                                    <Sparkles size={36} />
                                </div>
                                <div className="chat-empty-logo-ring" />
                                <div className="chat-empty-logo-ring chat-empty-logo-ring-2" />
                            </div>
                            <h2>FinSight AI</h2>
                            <p>Your intelligent finance document companion.<br />Attach PDFs and ask questions.</p>

                            <div className="chat-suggestions">
                                {SUGGESTIONS.map(({ icon: Icon, text }, i) => (
                                    <motion.button
                                        key={i}
                                        className="chat-suggestion"
                                        onClick={() => handleSend(text)}
                                        initial={{ opacity: 0, x: -16 }}
                                        animate={{ opacity: 1, x: 0, transition: { delay: 0.2 + i * 0.1 } }}
                                    >
                                        <Icon size={16} className="chat-suggestion-icon" />
                                        <span>{text}</span>
                                        <ArrowRight size={14} className="chat-suggestion-arrow" />
                                    </motion.button>
                                ))}
                            </div>
                        </motion.div>
                    ) : (
                        messages.map((msg, idx) => renderMessage(msg, idx))
                    )}
                </AnimatePresence>

                {/* Thinking State */}
                {(loading || ingesting) && (
                    <motion.div
                        className="chat-message assistant"
                        initial={{ opacity: 0, y: 16 }}
                        animate={{ opacity: 1, y: 0 }}
                    >
                        <div className="chat-message-avatar">
                            <div className="avatar-ai thinking"><Bot size={16} /></div>
                        </div>
                        <div className="chat-message-body">
                            <div className="chat-thinking">
                                <div className="chat-thinking-dots">
                                    <span /><span /><span />
                                </div>
                                <span className="chat-thinking-label">
                                    {ingesting ? ingestStep || 'Indexing documents...' : 'FinSight AI is analyzing your documents...'}
                                </span>
                            </div>
                        </div>
                    </motion.div>
                )}

                <div ref={messagesEndRef} />
            </div>

            {/* Input Area */}
            <div className="chat-input-container">
                {/* Attached Files Preview */}
                {attachedFiles.length > 0 && (
                    <div className="chat-attached-preview">
                        {attachedFiles.map((file, i) => (
                            <div key={i} className="chat-attached-preview-pill">
                                <FileText size={14} />
                                <span>{file.name}</span>
                                <button onClick={() => removeFile(i)} className="chat-attached-remove">
                                    <X size={12} />
                                </button>
                            </div>
                        ))}
                    </div>
                )}

                <div className="chat-input-wrapper">
                    <button
                        className="chat-attach-btn"
                        onClick={() => fileInputRef.current?.click()}
                        title="Attach PDF documents"
                    >
                        <Paperclip size={18} />
                    </button>
                    <input
                        ref={fileInputRef}
                        type="file"
                        accept=".pdf"
                        multiple
                        onChange={handleFileAttach}
                        style={{ display: 'none' }}
                    />
                    <textarea
                        ref={textareaRef}
                        className="chat-input"
                        rows={1}
                        placeholder="Ask a question or attach documents..."
                        value={input}
                        onChange={(e) => setInput(e.target.value)}
                        onKeyDown={handleKeyDown}
                        disabled={loading || ingesting}
                    />
                    <button
                        className="chat-send-btn"
                        onClick={() => handleSend()}
                        disabled={(!input.trim() && attachedFiles.length === 0) || loading || ingesting}
                    >
                        <Send size={16} />
                    </button>
                </div>
                <div className="chat-input-hint">
                    <kbd>Enter</kbd> to send · <kbd>Shift + Enter</kbd> for new line · <Paperclip size={10} /> to attach PDFs
                </div>
            </div>
        </div>
    );
}
