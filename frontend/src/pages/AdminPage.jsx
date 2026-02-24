import { useState, useEffect } from 'react';
import {
    BarChart3,
    Database,
    Cpu,
    AlertTriangle,
    Activity,
    RefreshCw,
    ChevronDown,
    ChevronRight,
    Clock,
    CheckCircle,
    XCircle,
} from 'lucide-react';
import { getTelemetryDashboard, getHealth } from '../api/client';
import '../styles/admin.css';

export default function AdminPage() {
    const [dashboard, setDashboard] = useState(null);
    const [health, setHealth] = useState(null);
    const [loading, setLoading] = useState(true);
    const [expandedQuery, setExpandedQuery] = useState(null);

    const fetchData = async () => {
        try {
            const [dash, h] = await Promise.all([
                getTelemetryDashboard(),
                getHealth(),
            ]);
            setDashboard(dash);
            setHealth(h);
        } catch (err) {
            console.error('Dashboard fetch failed:', err);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        fetchData();
        const interval = setInterval(fetchData, 30000);
        return () => clearInterval(interval);
    }, []);

    if (loading) {
        return (
            <div className="admin-page page-container">
                <div className="page-header">
                    <div>
                        <h1>Dashboard</h1>
                        <p>System telemetry and monitoring</p>
                    </div>
                </div>
                <div className="stats-grid">
                    {[1, 2, 3, 4].map((i) => (
                        <div key={i} className="glass-card-static stat-card">
                            <div className="skeleton" style={{ height: 36, width: '40%' }} />
                            <div className="skeleton" style={{ height: 12, width: '60%', marginTop: 10 }} />
                        </div>
                    ))}
                </div>
            </div>
        );
    }

    const counts = dashboard?.table_counts || {};
    const queries = dashboard?.query_logs || [];
    const errors = dashboard?.errors || [];

    const statCards = [
        { icon: Database, color: 'var(--accent-primary)', bg: 'var(--accent-primary-soft)', value: counts.query_logs || 0, label: 'Total Queries' },
        { icon: Activity, color: 'var(--accent-emerald)', bg: 'var(--success-soft)', value: counts.node_executions || 0, label: 'Node Executions' },
        { icon: Cpu, color: 'var(--accent-secondary)', bg: 'var(--accent-secondary-soft)', value: counts.llm_calls || 0, label: 'LLM Calls' },
        { icon: AlertTriangle, color: 'var(--error)', bg: 'var(--error-soft)', value: counts.errors || 0, label: 'Errors' },
    ];

    return (
        <div className="admin-page page-container">
            <div className="page-header">
                <div>
                    <h1>Dashboard</h1>
                    <p>System telemetry and monitoring</p>
                </div>
                <button className="btn-secondary" onClick={fetchData}>
                    <RefreshCw size={14} /> Refresh
                </button>
            </div>

            {/* Stats Grid */}
            <div className="stats-grid">
                {statCards.map(({ icon: Icon, color, bg, value, label }) => (
                    <div key={label} className="glass-card stat-card">
                        <div className="stat-icon" style={{ background: bg, color }}>
                            <Icon size={18} />
                        </div>
                        <div className="stat-value">{value}</div>
                        <div className="stat-label">{label}</div>
                    </div>
                ))}
            </div>

            {/* Health Status */}
            {health && (
                <div className="glass-card-static health-section">
                    <h2 className="admin-section-title"><Activity size={14} /> System Health</h2>
                    <div className="health-grid">
                        <div className="health-item">
                            <span className={`status-dot ${health.status === 'ok' ? 'online' : 'error'}`} />
                            <span>System: {health.status}</span>
                        </div>
                        <div className="health-item">
                            <span className={`status-dot ${health.groq_status === 'ok' ? 'online' : 'warning'}`} />
                            <span>Groq API: {health.groq_status}</span>
                        </div>
                        <div className="health-item">
                            <span className="status-dot online" />
                            <span>Telemetry: {health.telemetry_db}</span>
                        </div>
                        <div className="health-item">
                            <span className="status-dot online" />
                            <span>Indexed Docs: {health.indexed_documents}</span>
                        </div>
                    </div>
                </div>
            )}

            {/* Query Logs */}
            <div className="glass-card-static table-section">
                <h2 className="admin-section-title"><BarChart3 size={14} /> Recent Queries</h2>
                <div className="table-wrapper">
                    <table className="data-table">
                        <thead>
                            <tr>
                                <th style={{ width: 28 }}></th>
                                <th>Question</th>
                                <th>Type</th>
                                <th>Confidence</th>
                                <th>Latency</th>
                                <th>Status</th>
                                <th>Time</th>
                            </tr>
                        </thead>
                        <tbody>
                            {queries.map((q) => (
                                <tr
                                    key={q.id}
                                    className={expandedQuery === q.id ? 'expanded' : ''}
                                    onClick={() => setExpandedQuery(expandedQuery === q.id ? null : q.id)}
                                >
                                    <td>
                                        {expandedQuery === q.id ? <ChevronDown size={12} /> : <ChevronRight size={12} />}
                                    </td>
                                    <td className="table-question">{q.question}</td>
                                    <td><span className="badge badge-info">{q.query_type || '—'}</span></td>
                                    <td>
                                        {q.confidence != null ? (
                                            <span className={`badge ${q.confidence >= 0.7 ? 'badge-success' : q.confidence >= 0.4 ? 'badge-warning' : 'badge-error'}`}>
                                                {Math.round(q.confidence * 100)}%
                                            </span>
                                        ) : '—'}
                                    </td>
                                    <td className="mono">{q.total_latency_ms ? `${(q.total_latency_ms / 1000).toFixed(1)}s` : '—'}</td>
                                    <td>
                                        {q.status === 'completed' ? (
                                            <CheckCircle size={14} color="var(--success)" />
                                        ) : q.status === 'failed' ? (
                                            <XCircle size={14} color="var(--error)" />
                                        ) : (
                                            <Clock size={14} color="var(--warning)" />
                                        )}
                                    </td>
                                    <td className="mono">{new Date(q.created_at).toLocaleTimeString()}</td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>
            </div>

            {/* Errors */}
            {errors.length > 0 && (
                <div className="glass-card-static table-section errors-section">
                    <h2 className="admin-section-title"><AlertTriangle size={14} /> Recent Errors</h2>
                    <div className="errors-list">
                        {errors.slice(0, 10).map((err) => (
                            <div key={err.id} className="error-item">
                                <div className="error-header">
                                    <span className="badge badge-error">{err.error_type}</span>
                                    <span className="mono">{new Date(err.created_at).toLocaleString()}</span>
                                </div>
                                <p className="error-message">{err.error_message}</p>
                                {err.node_name && (
                                    <span className="error-node">Node: {err.node_name}</span>
                                )}
                            </div>
                        ))}
                    </div>
                </div>
            )}
        </div>
    );
}
