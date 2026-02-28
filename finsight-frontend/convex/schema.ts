import { defineSchema, defineTable } from "convex/server";
import { v } from "convex/values";

export default defineSchema({
    // Users: Syncs with Clerk authentication
    users: defineTable({
        clerkId: v.string(),     // external clerk ID
        email: v.string(),
        name: v.optional(v.string()),
        createdAt: v.number(),
    }).index("by_clerkId", ["clerkId"]),

    // Documents: Uploaded PDFs and their indexing status
    documents: defineTable({
        userId: v.id("users"),
        title: v.string(),
        filename: v.string(),
        storageId: v.optional(v.id("_storage")), // Convex cloud storage ID
        status: v.string(), // "indexing", "ready", "error"
        totalPages: v.optional(v.number()),
        treeDepth: v.optional(v.number()),
        nodeCount: v.optional(v.number()),
        errorMsg: v.optional(v.string()),
        createdAt: v.number(),
    }).index("by_userId", ["userId"]),

    // Trees: The generated PageIndex JSON structure 
    trees: defineTable({
        documentId: v.id("documents"),
        structure: v.any(), // The JSON hierarchical tree
    }).index("by_documentId", ["documentId"]),

    // Conversations: Chat threads
    conversations: defineTable({
        userId: v.id("users"),
        title: v.string(),
        documentIds: v.optional(v.array(v.string())), // docs attached to this chat
        createdAt: v.number(),
        updatedAt: v.number(),
    }).index("by_userId", ["userId"]),

    // Messages: Individual messages within a chat
    messages: defineTable({
        conversationId: v.id("conversations"),
        role: v.string(), // "user" or "assistant"
        content: v.string(),
        sources: v.optional(v.array(v.any())),
        confidence: v.optional(v.number()),
        latencyMs: v.optional(v.number()),
        queryType: v.optional(v.string()), // "simple", "complex", "multi_hop"
        createdAt: v.number(),
    }).index("by_conversationId", ["conversationId"]),

    // Telemetry: System logs and analytics (FastAPI pushes here)
    telemetry: defineTable({
        eventType: v.string(),   // "query_start", "node_end", "llm_call", "error"
        queryId: v.string(),
        nodeName: v.optional(v.string()),
        durationMs: v.optional(v.number()),
        details: v.optional(v.any()), // flexible JSON payload
        createdAt: v.number(),
    }).index("by_queryId", ["queryId"])
});
