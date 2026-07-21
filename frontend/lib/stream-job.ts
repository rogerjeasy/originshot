import { getIdToken } from "./firebase";
import type { Job } from "./types";

const BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

const TERMINAL = new Set(["done", "partial", "failed"]);

/**
 * Consume a job's Server-Sent Events progress stream.
 *
 * Each `data:` frame is a full job snapshot (same shape as `GET /api/jobs/{id}`); `onJob` is
 * called for every one, and the promise resolves when the stream ends — on a terminal status
 * or a server-side close. This is consumed with `fetch` rather than `EventSource` on purpose:
 * `EventSource` cannot send an `Authorization` header, and every route here is Bearer-authed,
 * so the token would otherwise have to travel in the URL. A network or HTTP error throws, so
 * the caller can fall back to polling — the stream is an optimisation over `GET /jobs/{id}`,
 * never the only way to learn a job's state.
 */
export async function streamJob(
  jobId: string,
  onJob: (job: Job) => void,
  signal?: AbortSignal,
): Promise<void> {
  const token = await getIdToken();
  const res = await fetch(`${BASE_URL}/api/jobs/${jobId}/stream`, {
    headers: token ? { Authorization: `Bearer ${token}` } : undefined,
    signal,
    cache: "no-store",
  });
  if (!res.ok || !res.body) throw new Error(`stream failed: ${res.status}`);

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  try {
    for (;;) {
      const { value, done } = await reader.read();
      if (done) return;
      buffer += decoder.decode(value, { stream: true });
      // SSE frames are separated by a blank line; keepalive comments (":") carry no data.
      let sep: number;
      while ((sep = buffer.indexOf("\n\n")) !== -1) {
        const frame = buffer.slice(0, sep);
        buffer = buffer.slice(sep + 2);
        for (const line of frame.split("\n")) {
          if (!line.startsWith("data:")) continue;
          try {
            const job = JSON.parse(line.slice(5).trim()) as Job;
            onJob(job);
            if (TERMINAL.has(job.status)) return;
          } catch {
            /* a malformed frame is skipped, never fatal */
          }
        }
      }
    }
  } finally {
    reader.releaseLock();
  }
}
