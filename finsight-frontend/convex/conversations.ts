import { mutation, query } from "./_generated/server";
import { v } from "convex/values";

// Create a new conversation if one doesn't exist
export const createConversation = mutation({
    args: {
        clerkId: v.string(),
        title: v.string(),
    },
    handler: async (ctx, args) => {
        let user = await ctx.db
            .query("users")
            .withIndex("by_clerkId", (q) => q.eq("clerkId", args.clerkId))
            .first();

        if (!user) throw new Error("User not found");

        const conversationId = await ctx.db.insert("conversations", {
            userId: user._id,
            title: args.title,
            createdAt: Date.now(),
            updatedAt: Date.now(),
        });

        return conversationId;
    },
});

export const listConversations = query({
    args: { clerkId: v.optional(v.string()) },
    handler: async (ctx, args) => {
        if (!args.clerkId) return [];

        const user = await ctx.db
            .query("users")
            .withIndex("by_clerkId", (q) => q.eq("clerkId", args.clerkId!))
            .first();

        if (!user) return [];

        return await ctx.db
            .query("conversations")
            .withIndex("by_userId", (q) => q.eq("userId", user._id))
            .order("desc")
            .collect();
    }
});

// Get conversation details (does not include messages, fetch those separately)
export const getConversation = query({
    args: { conversationId: v.id("conversations") },
    handler: async (ctx, args) => {
        return await ctx.db.get(args.conversationId);
    }
});

// Attach a document to a conversation scope
export const attachDocument = mutation({
    args: {
        conversationId: v.id("conversations"),
        documentId: v.string(), // We store just the string ID for simplicity
    },
    handler: async (ctx, args) => {
        const conv = await ctx.db.get(args.conversationId);
        if (!conv) throw new Error("Conversation not found");

        const currentDocs = conv.documentIds || [];
        if (!currentDocs.includes(args.documentId)) {
            await ctx.db.patch(args.conversationId, {
                documentIds: [...currentDocs, args.documentId],
                updatedAt: Date.now(),
            });
        }
    }
});

export const deleteConversation = mutation({
    args: { conversationId: v.id("conversations") },
    handler: async (ctx, args) => {
        // Delete all messages in the conversation
        const messages = await ctx.db
            .query("messages")
            .withIndex("by_conversationId", (q) => q.eq("conversationId", args.conversationId))
            .collect();

        for (const msg of messages) {
            await ctx.db.delete(msg._id);
        }

        // Delete the conversation itself
        await ctx.db.delete(args.conversationId);
    }
});
