import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Standalone output for Docker / Vercel edge deployment
  output: "standalone",

  // Proxy /api/backend/* to the FastAPI backend to avoid CORS in production
  async rewrites() {
    const backendUrl =
      process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
    return [
      {
        source: "/api/backend/:path*",
        destination: `${backendUrl}/:path*`,
      },
    ];
  },
};

export default nextConfig;
