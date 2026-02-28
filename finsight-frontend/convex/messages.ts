import { mutation, query } from "./_generated/server";
import { v } from "convex/values";

// Frontend users send messages
export const sendMessage = mutation({
    args: {
        conversationId: v.id("conversations"),
        content: v.string(),
    },
    handler: async (ctx, args) => {
        // Insert user's message
        const messageId = await ctx.db.insert("messages", {
            conversationId: args.conversationId,
            role: "user",
            content: args.content,
            createdAt: Date.now(),
        });

        // Update conversation timestamp
        await ctx.db.patch(args.conversationId, { updatedAt: Date.now() });

        return messageId;
    },
});

// Backend agent sends its reply with metrics
export const saveAgentResponse = mutation({
    args: {
        conversationId: v.id("conversations"),
        content: v.string(),
        sources: v.optional(v.array(v.any())),
        confidence: v.optional(v.number()),
        latencyMs: v.optional(v.number()),
        queryType: v.optional(v.string()),
    },
    handler: async (ctx, args) => {
        const messageId = await ctx.db.insert("messages", {
            conversationId: args.conversationId,
            role: "assistant",
            content: args.content,
            sources: args.sources,
            confidence: args.confidence,
            latencyMs: args.latencyMs,
            queryType: args.queryType,
            createdAt: Date.now(),
        });

        await ctx.db.patch(args.conversationId, { updatedAt: Date.now() });
        return messageId;
    },
});

export const listMessages = query({
    args: { conversationId: v.id("conversations") },
    handler: async (ctx, args) => {
        const messages = await ctx.db
            .query("messages")
            .withIndex("by_conversationId", (q) => q.eq("conversationId", args.conversationId))
            .order("asc")
            .collect();

        return messages;
    }
});
