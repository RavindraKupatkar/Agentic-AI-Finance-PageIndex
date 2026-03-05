// Convex auth configuration for Clerk
// This file is used by Convex to validate Clerk JWT tokens
/**
 * Convex Auth Configuration — Clerk Integration
 *
 * IMPORTANT: Environment variables in Convex config files are set via the
 * Convex Dashboard (Settings → Environment Variables), NOT from .env files.
 * Set CLERK_ISSUER_URL in the Convex Dashboard to your Clerk issuer URL.
 */
export default {
    providers: [
        {
            domain: process.env.CLERK_ISSUER_URL!,
            applicationID: "convex",
        },
    ],
};
