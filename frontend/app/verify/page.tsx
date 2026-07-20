"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { ArrowRight, Scale, ShieldCheck } from "lucide-react";

import { apiFetch } from "@/lib/api";
import type { VerifyResult } from "@/lib/types";
import { AdaptiveChrome } from "@/components/adaptive-chrome";
import { FadeIn } from "@/components/motion/fade-in";
import { TamperDemo } from "@/components/tamper-demo";
import { UploadDropzone } from "@/components/upload-dropzone";
import { VerifyPanel } from "@/components/verify-panel";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { MediaSkeleton } from "@/components/ui/skeleton";

const SHA256 = /^[a-f0-9]{64}$/i;

/**
 * The provenance bench.
 *
 * The previous version put the two ways in behind a segmented control, which
 * made them mutually exclusive and hid one of them at all times. They are not
 * alternatives in any meaningful sense — one takes a file, one takes a string,
 * and both fit on the screen at once. Removing the toggle removes a piece of
 * state, a radiogroup, and the moment where switching modes silently discarded
 * a result the reader was still looking at.
 *
 * What remains is a hierarchy instead of a choice: dropping a file is the
 * primary act and gets the full plate, looking a hash up is a one-line
 * secondary, and the two supporting pieces — the tamper demonstration and the
 * route into Resolve — sit below a rule as clearly subordinate.
 */
export default function VerifyHome() {
  const router = useRouter();
  const [sha, setSha] = useState("");
  const [shaError, setShaError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<VerifyResult | null>(null);

  async function verifyFile(file: File) {
    setBusy(true);
    setError(null);
    setResult(null);
    try {
      const fd = new FormData();
      fd.append("file", file);
      setResult(await apiFetch<VerifyResult>("/api/verify", { method: "POST", body: fd }));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Couldn't verify that file");
    } finally {
      setBusy(false);
    }
  }

  function submitHash(e: React.FormEvent) {
    e.preventDefault();
    const value = sha.trim();
    if (!SHA256.test(value)) {
      setShaError("A hash is 64 hexadecimal characters.");
      return;
    }
    setShaError(null);
    router.push(`/verify/${value.toLowerCase()}`);
  }

  return (
    <AdaptiveChrome ground="ink">
      <div className="mx-auto max-w-3xl px-4 py-12 sm:px-6 sm:py-16">
        <FadeIn className="mb-10">
          <p className="kicker t-verify inline-flex items-center gap-2">
            <ShieldCheck className="size-3.5" aria-hidden />
            Provenance check
          </p>
          <h1 className="display-face mt-4 text-[clamp(1.875rem,4.5vw,2.75rem)]">
            Verify provenance
          </h1>
          <p className="mt-5 max-w-2xl text-[16.5px] leading-relaxed text-muted-foreground">
            Drop a file and we re-hash the bytes and re-read its embedded manifest. Nothing you
            drop here is uploaded or kept — it is read in memory to check it, then dropped.
          </p>
        </FadeIn>

        {/* ── The bench ──────────────────────────────────────────────────── */}
        <FadeIn>
          <section className="surface overflow-hidden rounded-xl border bg-card">
            <div className="flex flex-wrap items-baseline justify-between gap-x-6 gap-y-1 border-b px-5 py-3.5">
              <p className="kicker text-muted-foreground">Check a file</p>
              <p className="kicker text-muted-foreground">image or mp4</p>
            </div>

            <div className="p-5 sm:p-6">
              <UploadDropzone
                onFile={verifyFile}
                busy={busy}
                title="Drop a file to verify"
                subtitle="We re-extract the manifest and re-hash the content"
                cta="Choose file"
                accept="image/*,video/mp4"
                requireImage={false}
              />
            </div>

            {/* The second way in. A one-line form, always visible, rather than a
                mode the reader has to discover behind a toggle. */}
            <form
              onSubmit={submitHash}
              className="border-t bg-muted/40 px-5 py-4"
              aria-describedby={shaError ? "sha-error" : undefined}
            >
              <label htmlFor="sha-input" className="kicker text-muted-foreground">
                Or look up a hash you already have
              </label>
              <div className="mt-2.5 flex flex-col gap-2.5 sm:flex-row">
                <Input
                  id="sha-input"
                  value={sha}
                  onChange={(e) => {
                    setSha(e.target.value);
                    if (shaError) setShaError(null);
                  }}
                  placeholder="64 hex characters"
                  className="font-mono sm:flex-1"
                  aria-invalid={shaError ? true : undefined}
                  aria-describedby={shaError ? "sha-error" : undefined}
                  autoComplete="off"
                  spellCheck={false}
                />
                <Button type="submit" variant="accent" className="sm:shrink-0">
                  Look up
                  <ArrowRight className="size-4" />
                </Button>
              </div>
              {shaError && (
                <p id="sha-error" className="mt-2 text-xs text-danger">
                  {shaError}
                </p>
              )}
            </form>
          </section>
        </FadeIn>

        {/* ── The verdict ────────────────────────────────────────────────── */}
        {/* These all carry their own paper surface, so they need `surface` to
            shift the inherited text tokens back off the ink ground. */}
        {busy && (
          <div className="surface mt-4">
            <MediaSkeleton aspect="aspect-[3/1]" />
          </div>
        )}
        {error && (
          <div className="surface mt-4">
            <Alert title="Couldn't verify that file">{error}</Alert>
          </div>
        )}
        {result && (
          <FadeIn className="surface mt-4">
            <VerifyPanel result={result} />
          </FadeIn>
        )}

        {/* ── Supporting, and clearly subordinate ────────────────────────── */}
        <div className="mt-14">
          <div className="kelvin-rule" aria-hidden />
          <p className="kicker mt-6 text-muted-foreground">If you want to test it</p>

          <FadeIn className="surface mt-4">
            <TamperDemo />
          </FadeIn>

          {/* Most people verifying a listing photo are already in an argument
              about it. Hand them the tool built for that rather than leaving
              them at a verdict. */}
          <FadeIn delay={0.06} className="mt-4">
            <Link
              href="/resolve"
              className="surface group flex items-start gap-3.5 rounded-xl border bg-card p-5 transition-colors hover:bg-secondary"
            >
              <Scale className="t-accent mt-0.5 size-4 shrink-0" aria-hidden />
              <span className="min-w-0 flex-1">
                <span className="block text-[14.5px] font-medium">
                  Received something that doesn&apos;t match the listing?
                </span>
                <span className="mt-1 block text-[13.5px] leading-relaxed text-muted-foreground">
                  Resolve compares the item that arrived against the seller&apos;s authentic
                  original and issues an evidence report you can attach to a claim.
                </span>
              </span>
              <ArrowRight
                className="mt-0.5 size-4 shrink-0 text-muted-foreground transition-transform group-hover:translate-x-0.5"
                aria-hidden
              />
            </Link>
          </FadeIn>
        </div>
      </div>
    </AdaptiveChrome>
  );
}
