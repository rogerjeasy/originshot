import { config } from "dotenv";
import { fileURLToPath } from "node:url";
import { dirname, resolve } from "node:path";

// Load the single repo-root .env (listsnap/.env), shared with the backend, before Next.js
// snapshots NEXT_PUBLIC_* for the client bundle. In production (Vercel, Root Directory =
// frontend) that file doesn't exist, so dotenv is a silent no-op and the dashboard env vars
// are used. dotenv never overrides an already-set process.env var, so the platform always wins.
config({ path: resolve(dirname(fileURLToPath(import.meta.url)), "../.env") });

/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
};

export default nextConfig;
