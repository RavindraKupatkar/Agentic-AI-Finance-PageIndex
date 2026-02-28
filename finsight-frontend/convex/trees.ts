import { mutation, query } from "./_generated/server";
import { v } from "convex/values";

// Used by Python Backend to store the generated PageIndex
export const saveTree = mutation({
    args: {
        documentId: v.id("documents"),
        structure: v.any()
    },
    handler: async (ctx, args) => {
        // Delete any existing tree for this doc
        const existing = await ctx.db
            .query("trees")
            .withIndex("by_documentId", q => q.eq("documentId", args.documentId))
            .first();

        if (existing) {
            await ctx.db.delete(existing._id);
        }

        const treeId = await ctx.db.insert("trees", {
            documentId: args.documentId,
            structure: args.structure,
        });

        return treeId;
    }
});

// Used by Python Backend to fetch the PageIndex to search over
export const getTree = query({
    args: {
        documentId: v.id("documents"),
    },
    handler: async (ctx, args) => {
        return await ctx.db
            .query("trees")
            .withIndex("by_documentId", q => q.eq("documentId", args.documentId))
            .first();
    }
});
