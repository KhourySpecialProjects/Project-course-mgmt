import type { NextConfig } from "next";

// Where the API lives, as seen from the Next.js server (not the browser).
// In Docker Compose this is http://api:8000; running locally it's localhost.
const apiUrl = process.env.API_INTERNAL_URL ?? "http://localhost:8000";

// When the dev server runs in Docker on Windows or macOS, saving a file on
// your computer doesn't notify the container, so the dev server checks for
// changes on a timer instead. docker-compose.yml sets this; `npm run dev`
// directly on your computer doesn't need it.
const pollIntervalMs = Number(process.env.WATCH_POLL_INTERVAL_MS) || undefined;

const nextConfig: NextConfig = {
  // Produces a small self-contained server in .next/standalone for the
  // production Docker image.
  output: "standalone",
  ...(pollIntervalMs ? { watchOptions: { pollIntervalMs } } : {}),
  // The browser calls /api/... on the SAME origin as the web app, and Next.js
  // forwards ("rewrites") those requests to the API container. Same origin
  // means the login cookie just works, with no CORS configuration.
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${apiUrl}/api/:path*` }];
  },
};

export default nextConfig;
