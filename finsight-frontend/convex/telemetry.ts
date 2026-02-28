import { mutation } from "./_generated/server";
import { v } from "convex/values";

export const logEvent = mutation({
    args: {
        eventType: v.string(),
        queryId: v.string(),
        nodeName: v.optional(v.string()),
        durationMs: v.optional(v.number()),
        details: v.optional(v.any())
    },
    handler: async (ctx, args) => {
        await ctx.db.insert("telemetry", {
            eventType: args.eventType,
            queryId: args.queryId,
            nodeName: args.nodeName,
            durationMs: args.durationMs,
            details: args.details,
            createdAt: Date.now()
        });
    }
});
