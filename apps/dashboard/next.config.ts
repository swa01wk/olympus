import type { NextConfig } from "next";

const dataMode = process.env.NEXT_PUBLIC_OLYMPUS_DATA_MODE ?? "fixture";
const isProd = process.env.NODE_ENV === "production";
const demoBuild = process.env.OLYMPUS_DEMO_BUILD === "1";

if (isProd && dataMode === "fixture" && !demoBuild) {
  throw new Error(
    "Production build with NEXT_PUBLIC_OLYMPUS_DATA_MODE=fixture is forbidden. Set OLYMPUS_DEMO_BUILD=1 for demo builds only.",
  );
}

const nextConfig: NextConfig = {
  reactStrictMode: true,
  /** Playwright and some proxies hit 127.0.0.1; allow dev chunks/HMR without cross-origin blocks. */
  allowedDevOrigins: ["127.0.0.1", "localhost"],
};

export default nextConfig;
