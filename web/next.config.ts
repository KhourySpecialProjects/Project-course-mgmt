import type { NextConfig } from "next";

// Where the API lives, as seen from the Next.js server (not the browser).
// In Docker Compose this is http://api:8000; running locally it's localhost.
const apiUrl = process.env.API_INTERNAL_URL ?? "http://localhost:8000";

const nextConfig: NextConfig = {
  // Produces a small self-contained server in .next/standalone for the
  // production Docker image.
  output: "standalone",
  // The browser calls /api/... on the SAME origin as the web app, and Next.js
  // forwards ("rewrites") those requests to the API container. Same origin
  // means the login cookie just works, with no CORS configuration.
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${apiUrl}/api/:path*` }];
  },
};

export default nextConfig;
