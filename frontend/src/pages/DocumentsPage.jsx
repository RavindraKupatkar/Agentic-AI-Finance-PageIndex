import { useState, useEffect } from 'react';
import { FileText, Loader2, CheckCircle, TreePine, Clock, File, Layers } from 'lucide-react';
import { listDocuments } from '../api/client';
import '../styles/documents.css';

export default function DocumentsPage() {
    const [documents, setDocuments] = useState([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);

    useEffect(() => {
        fetchDocuments();
    }, []);

    const fetchDocuments = async () => {
        try {
            setLoading(true);
            setError(null);
            const data = await listDocuments();
            setDocuments(data);
        } catch (err) {
            setError(err.message || 'Failed to load documents');
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="docs-page">
            <div className="docs-header">
                <div className="docs-header-text">
                    <h1>Your Documents</h1>
                    <p>Documents you've indexed through the chat. Attach PDFs in the chat to add more.</p>
                </div>
                <div className="docs-stats">
                    <div className="docs-stat">
                        <Layers size={16} />
                        <span className="docs-stat-value">{documents.length}</span>
                        <span className="docs-stat-label">Indexed</span>
                    </div>
                </div>
            </div>

            {loading && (
                <div className="docs-loading">
                    <Loader2 size={24} className="spin" />
                    <span>Loading documents...</span>
                </div>
            )}

            {error && (
                <div className="docs-error">
                    <p>{error}</p>
                    <button onClick={fetchDocuments}>Retry</button>
                </div>
            )}

            {!loading && !error && documents.length === 0 && (
                <div className="docs-empty">
                    <div className="docs-empty-icon">
                        <FileText size={40} />
                    </div>
                    <h3>No documents indexed yet</h3>
                    <p>
                        Go to <strong>Chat</strong> and attach PDF documents using the
                        <span className="docs-empty-icon-inline">📎</span> button to get started.
                    </p>
                </div>
            )}

            {!loading && !error && documents.length > 0 && (
                <div className="docs-grid">
                    {documents.map((doc) => (
                        <div key={doc.doc_id} className="docs-card">
                            <div className="docs-card-icon">
                                <File size={24} />
                            </div>
                            <div className="docs-card-info">
                                <h3 className="docs-card-title">{doc.title || doc.filename}</h3>
                                <p className="docs-card-filename">{doc.filename}</p>
                                <div className="docs-card-meta">
                                    <span className="docs-card-meta-item">
                                        <FileText size={12} />
                                        {doc.total_pages} pages
                                    </span>
                                    <span className="docs-card-meta-item">
                                        <CheckCircle size={12} />
                                        Indexed
                                    </span>
                                </div>
                            </div>
                        </div>
                    ))}
                </div>
            )}

            {/* How Indexing Works */}
            <div className="docs-indexing-info">
                <h3>How FinSight Indexes Your Documents</h3>
                <div className="docs-pipeline">
                    <div className="docs-pipeline-step">
                        <div className="docs-pipeline-step-icon step-1">
                            <FileText size={18} />
                        </div>
                        <span>Validate</span>
                        <p>PDF format & size check</p>
                    </div>
                    <div className="docs-pipeline-connector" />
                    <div className="docs-pipeline-step">
                        <div className="docs-pipeline-step-icon step-2">
                            <Layers size={18} />
                        </div>
                        <span>Extract</span>
                        <p>Pages, metadata & tables</p>
                    </div>
                    <div className="docs-pipeline-connector" />
                    <div className="docs-pipeline-step">
                        <div className="docs-pipeline-step-icon step-3">
                            <TreePine size={18} />
                        </div>
                        <span>Build Tree</span>
                        <p>AI-generated topic index</p>
                    </div>
                    <div className="docs-pipeline-connector" />
                    <div className="docs-pipeline-step">
                        <div className="docs-pipeline-step-icon step-4">
                            <CheckCircle size={18} />
                        </div>
                        <span>Ready</span>
                        <p>Searchable & queryable</p>
                    </div>
                </div>
            </div>
        </div>
    );
}
