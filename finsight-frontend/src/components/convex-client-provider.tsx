"use client";

import { ClerkProvider, useAuth } from "@clerk/nextjs";
import { ConvexProviderWithClerk } from "convex/react-clerk";
import { ConvexReactClient } from "convex/react";
import { ReactNode } from "react";

const convexUrl = process.env.NEXT_PUBLIC_CONVEX_URL;
const clerkKey = process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY;

if (!convexUrl) {
    throw new Error(
        "Missing NEXT_PUBLIC_CONVEX_URL environment variable. " +
        "Set it in .env.local or your deployment environment."
    );
}

if (!clerkKey) {
    throw new Error(
        "Missing NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY environment variable. " +
        "Set it in .env.local or your deployment environment."
    );
}

const convex = new ConvexReactClient(convexUrl);

export default function ConvexClientProvider({
    children,
}: {
    children: ReactNode;
}) {
    return (
        <ClerkProvider publishableKey={clerkKey}>
            <ConvexProviderWithClerk client={convex} useAuth={useAuth}>
                {children}
            </ConvexProviderWithClerk>
        </ClerkProvider>
    );
}
