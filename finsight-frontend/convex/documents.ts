import { mutation, query } from "./_generated/server";
import { v } from "convex/values";

// Create a new document metadata entry
export const createDocument = mutation({
    args: {
        clerkId: v.string(),
        title: v.string(),
        filename: v.string(),
        storageId: v.optional(v.id("_storage")),
    },
    handler: async (ctx, args) => {
        // 1. Get user record or create it
        let user = await ctx.db
            .query("users")
            .withIndex("by_clerkId", (q) => q.eq("clerkId", args.clerkId))
            .first();

        if (!user) {
            const userId = await ctx.db.insert("users", {
                clerkId: args.clerkId,
                email: "unknown@example.com", // update later on webhook
                createdAt: Date.now(),
            });
            user = await ctx.db.get(userId);
        }

        // 2. Insert document record
        const documentId = await ctx.db.insert("documents", {
            userId: user!._id,
            title: args.title,
            filename: args.filename,
            storageId: args.storageId,
            status: "indexing",
            createdAt: Date.now(),
        });

        return documentId;
    },
});

export const listDocuments = query({
    args: { clerkId: v.optional(v.string()) },
    handler: async (ctx, args) => {
        if (!args.clerkId) return [];

        const user = await ctx.db
            .query("users")
            .withIndex("by_clerkId", (q) => q.eq("clerkId", args.clerkId!))
            .first();

        if (!user) return [];

        const documents = await ctx.db
            .query("documents")
            .withIndex("by_userId", (q) => q.eq("userId", user._id))
            .order("desc")
            .collect();

        return documents;
    },
});

export const updateDocumentStatus = mutation({
    args: {
        documentId: v.id("documents"),
        status: v.string(),
        totalPages: v.optional(v.number()),
        treeDepth: v.optional(v.number()),
        nodeCount: v.optional(v.number()),
        errorMsg: v.optional(v.string())
    },
    handler: async (ctx, args) => {
        await ctx.db.patch(args.documentId, {
            status: args.status,
            totalPages: args.totalPages,
            treeDepth: args.treeDepth,
            nodeCount: args.nodeCount,
            errorMsg: args.errorMsg
        });
    }
});

// Used by Python backend to get an upload URL for saving PDFs
export const generateUploadUrl = mutation(async (ctx) => {
    return await ctx.storage.generateUploadUrl();
});

// Used by Python backend to get a download URL for a stored PDF
export const getDownloadUrl = query({
    args: { storageId: v.id("_storage") },
    handler: async (ctx, args) => {
        return await ctx.storage.getUrl(args.storageId);
    },
});

