import { NavLink, useLocation } from 'react-router-dom';
import {
    MessageSquare,
    FileText,
    Sparkles,
    Plus,
    Trash2,
    Paperclip,
    Clock,
} from 'lucide-react';
import { useState, useEffect } from 'react';
import { listConversations, createConversation, deleteConversation } from '../../api/client';
import '../../styles/layout.css';

const NAV_ITEMS = [
    { to: '/chat', icon: MessageSquare, label: 'Chat' },
    { to: '/documents', icon: FileText, label: 'Your Documents' },
];

export default function Sidebar({ onConversationSelect, activeConversationId }) {
    const location = useLocation();
    const isLanding = location.pathname === '/';
    const [conversations, setConversations] = useState([]);
    const [loading, setLoading] = useState(false);

    useEffect(() => {
        fetchConversations();
    }, []);

    const fetchConversations = async () => {
        try {
            setLoading(true);
            const data = await listConversations();
            setConversations(data);
        } catch {
            // silent
        } finally {
            setLoading(false);
        }
    };

    const handleNewChat = async () => {
        try {
            const conv = await createConversation();
            await fetchConversations();
            if (onConversationSelect) onConversationSelect(conv.id);
        } catch {
            // silent
        }
    };

    const handleDelete = async (e, convId) => {
        e.stopPropagation();
        try {
            await deleteConversation(convId);
            setConversations(prev => prev.filter(c => c.id !== convId));
            if (activeConversationId === convId && onConversationSelect) {
                onConversationSelect(null);
            }
        } catch {
            // silent
        }
    };

    if (isLanding) return null;

    return (
        <aside className="sidebar">
            <div className="sidebar-brand">
                <div className="sidebar-brand-icon">
                    <Sparkles size={18} />
                </div>
                <div className="sidebar-brand-text">
                    <h1>FinSight</h1>
                    <span>by SyncroAI</span>
                </div>
            </div>

            <nav className="sidebar-nav">
                {NAV_ITEMS.map(({ to, icon: Icon, label }) => (
                    <NavLink
                        key={to}
                        to={to}
                        className={({ isActive }) =>
                            `sidebar-link ${isActive ? 'active' : ''}`
                        }
                    >
                        <Icon size={18} />
                        <span>{label}</span>
                    </NavLink>
                ))}
            </nav>

            {/* Chat History */}
            <div className="sidebar-history">
                <div className="sidebar-history-header">
                    <div className="sidebar-history-title">
                        <Clock size={14} />
                        <span>History</span>
                    </div>
                    <button className="sidebar-new-chat" onClick={handleNewChat} title="New Chat">
                        <Plus size={14} />
                    </button>
                </div>

                <div className="sidebar-history-list">
                    {loading && <div className="sidebar-history-loading">Loading...</div>}
                    {!loading && conversations.length === 0 && (
                        <div className="sidebar-history-empty">No conversations yet</div>
                    )}
                    {conversations.map(conv => (
                        <button
                            key={conv.id}
                            className={`sidebar-history-item ${activeConversationId === conv.id ? 'active' : ''}`}
                            onClick={() => onConversationSelect?.(conv.id)}
                        >
                            <div className="sidebar-history-item-content">
                                <span className="sidebar-history-item-title">
                                    {conv.first_question || conv.title || 'New Conversation'}
                                </span>
                                {conv.documents && conv.documents.length > 0 && (
                                    <span className="sidebar-history-item-docs">
                                        <Paperclip size={10} />
                                        {conv.documents.length} doc{conv.documents.length > 1 ? 's' : ''}
                                    </span>
                                )}
                            </div>
                            <button
                                className="sidebar-history-delete"
                                onClick={(e) => handleDelete(e, conv.id)}
                                title="Delete"
                            >
                                <Trash2 size={12} />
                            </button>
                        </button>
                    ))}
                </div>
            </div>
        </aside>
    );
}
