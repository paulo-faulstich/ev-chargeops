import type { NextConfig } from "next";

if (process.env.AUTH_MODE === "fixture" && process.env.NODE_ENV === "production") {
  throw new Error("Fixture authentication is disabled in production.");
}

const nextConfig: NextConfig = {
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: `${process.env.API_PROXY_TARGET ?? "http://127.0.0.1:8000"}/:path*`,
      },
    ];
  },
};

export default nextConfig;
