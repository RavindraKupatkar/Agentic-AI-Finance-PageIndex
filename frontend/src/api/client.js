import axios from 'axios';

const API_BASE = 'http://127.0.0.1:8000/api/v1';

const client = axios.create({
    baseURL: API_BASE,
    timeout: 300000,
    headers: { 'Content-Type': 'application/json' },
});

// ─── Query ───────────────────────────────────
export async function queryDocuments(question, threadId = 'default') {
    const { data } = await client.post('/pageindex/query', {
        question,
        thread_id: threadId,
    });
    return data;
}

// ─── Ingest ──────────────────────────────────
export async function ingestPDF(file, onProgress) {
    const formData = new FormData();
    formData.append('file', file);

    const { data } = await client.post('/pageindex/ingest', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
        onUploadProgress: (e) => {
            if (onProgress && e.total) {
                onProgress(Math.round((e.loaded / e.total) * 100));
            }
        },
    });
    return data;
}

// ─── Documents ───────────────────────────────
export async function listDocuments() {
    const { data } = await client.get('/pageindex/documents');
    return data;
}

// ─── Page Content (Clickable Citations) ──────
export async function getPageContent(docId, pageNum) {
    const { data } = await client.get(`/pageindex/page/${docId}/${pageNum}`);
    return data;
}

// ─── Conversations ───────────────────────────
export async function listConversations(limit = 50) {
    const { data } = await client.get('/conversations', { params: { limit } });
    return data;
}

export async function createConversation(title = 'New Conversation') {
    const { data } = await client.post('/conversations', { title });
    return data;
}

export async function getConversation(convId) {
    const { data } = await client.get(`/conversations/${convId}`);
    return data;
}

export async function addMessage(convId, role, content, sources = null, confidence = null, latencyMs = null) {
    const { data } = await client.post(`/conversations/${convId}/message`, {
        role,
        content,
        sources,
        confidence,
        latency_ms: latencyMs,
    });
    return data;
}

export async function attachDocument(convId, docId, filename, totalPages = 0) {
    const { data } = await client.post(`/conversations/${convId}/document`, {
        doc_id: docId,
        filename,
        total_pages: totalPages,
    });
    return data;
}

export async function deleteConversation(convId) {
    const { data } = await client.delete(`/conversations/${convId}`);
    return data;
}

// ─── Health ──────────────────────────────────
export async function getHealth() {
    const { data } = await client.get('/pageindex/health');
    return data;
}
