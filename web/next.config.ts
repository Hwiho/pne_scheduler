import type { NextConfig } from "next";

// The API runs as a separate process on the same machine (see WEB_PORT_PLAN §3).
// Proxying keeps the browser on one origin, so there is no CORS surface and no
// reason for the API to accept requests from anywhere else.
const API = process.env.PNE_API ?? "http://127.0.0.1:8000";

const config: NextConfig = {
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${API}/api/:path*` }];
  },
};

export default config;
