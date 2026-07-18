"use client";

import { useState } from "react";
import { FlaskConical, Loader2 } from "lucide-react";

import { apiFetch } from "@/lib/api";
import type { VerifyResult } from "@/lib/types";
import { FadeIn } from "@/components/motion/fade-in";
import { VerifyPanel } from "@/components/verify-panel";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";

// The hero video, byte-for-byte from B2 with its manifest embedded — the one demo file
// whose content binding is intact by construction (see lib/demo-assets.ts).
const DEMO_FILE = "/demo/video-6ae12d1e.mp4";

async function verifyBytes(bytes: Uint8Array, name: string): Promise<VerifyResult> {
  const fd = new FormData();
  fd.append("file", new File([new Blob([bytes.buffer as ArrayBuffer])], name, { type: "video/mp4" }));
  return apiFetch<VerifyResult>("/api/verify", { method: "POST", body: fd });
}

/**
 * The marquee moment, self-serve: verify a real generated file, then flip ONE byte of it
 * in the browser and watch `content_bound` break. Everything runs against the same public
 * /api/verify endpoint a skeptic would use — there is no special demo path to distrust.
 */
export function TamperDemo() {
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [intact, setIntact] = useState<VerifyResult | null>(null);
  const [tampered, setTampered] = useState<VerifyResult | null>(null);

  async function run() {
    setError(null);
    setIntact(null);
    setTampered(null);
    try {
      setBusy("Fetching a real generated file…");
      const buf = new Uint8Array(await (await fetch(DEMO_FILE)).arrayBuffer());

      setBusy("Verifying the intact file…");
      setIntact(await verifyBytes(buf, "hero-video.mp4"));

      setBusy("Flipping one byte and re-verifying…");
      const evil = buf.slice();
      const at = Math.floor(evil.length * 0.33); // media content, well clear of the manifest box
      evil[at] ^= 0xff;
      setTampered(await verifyBytes(evil, "hero-video-tampered.mp4"));
    } catch (e) {
      setError(e instanceof Error ? e.message : "The demo could not run");
    } finally {
      setBusy(null);
    }
  }

  return (
    <div className="rounded-lg border bg-card p-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="min-w-0">
          <p className="font-semibold tracking-tight">No file handy? Try to fool it.</p>
          <p className="mt-0.5 text-sm text-muted-foreground">
            We&apos;ll verify a real generated video, flip a single byte of it in your
            browser, and verify it again.
          </p>
        </div>
        <Button variant="outline" onClick={run} disabled={busy !== null}>
          {busy ? <Loader2 className="animate-spin" /> : <FlaskConical />}
          {busy ?? "Run the tamper test"}
        </Button>
      </div>

      {error && <Alert className="mt-4">{error}</Alert>}

      {/* Stacked, not side-by-side: the page column is narrow, and the story is
          sequential anyway — the same certificate turning red. */}
      {(intact || tampered) && (
        <div className="mt-5 grid gap-4">
          {intact && (
            <FadeIn>
              <p className="label mb-2 text-muted-foreground">1 · The file as generated</p>
              <VerifyPanel result={intact} />
            </FadeIn>
          )}
          {tampered && (
            <FadeIn>
              <p className="label mb-2 text-muted-foreground">
                2 · Same file, one byte flipped
              </p>
              <VerifyPanel result={tampered} />
            </FadeIn>
          )}
        </div>
      )}
    </div>
  );
}
