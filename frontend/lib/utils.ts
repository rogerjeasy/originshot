import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

/** Truncate a hash for display: 7f3a…b1c4 */
export function shortHash(sha?: string | null, head = 4, tail = 4): string {
  if (!sha) return "—";
  if (sha.length <= head + tail + 1) return sha;
  return `${sha.slice(0, head)}…${sha.slice(-tail)}`;
}
