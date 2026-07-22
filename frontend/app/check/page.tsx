"use client";

import { useState } from "react";
import Link from "next/link";
import { ArrowRight, Link2, ScanSearch, Scale } from "lucide-react";

import { apiFetch } from "@/lib/api";
import type { CheckResult } from "@/lib/types";
import { AdaptiveChrome } from "@/components/adaptive-chrome";
import { FadeIn } from "@/components/motion/fade-in";
import { UploadDropzone } from "@/components/upload-dropzone";
import { VerifyPanel } from "@/components/verify-panel";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { MediaSkeleton } from "@/components/ui/skeleton";

/**
 * Verify Anywhere — the buyer's bench.
 *
 * `/verify` is written for someone who already holds a file they got from us. A buyer looking
 * at a listing on another site holds neither the file nor an account: they have a link, or at
 * most the photo they can drag off the page. This page meets them there. Under the hood it is
 * the same verification core as `/verify` (POST /api/check → verify_bytes), so the perceptual
 * "Verify in the Wild" tier can still recognise the re-encoded, manifest-stripped copy a
 * marketplace actually serves and trace it back to a known OriginShot asset.
 *
 * Pasting a link is the primary act (it is what a buyer naturally has); dropping the photo is
 * the always-visible alternative for the surfaces that block hot-linking.
 */
const SOURCE_NOTE: Record<CheckResult["source"], (n: number) => string> = {
  upload: () => "Checked the photo you dropped.",
  url_image: () => "Checked the image at that link.",
  listing_page: (n) => `Read that page and checked ${n} photo${n === 1 ? "" : "s"} on it.`,
};

export default function CheckHome() {
  const [url, setUrl] = useState("");
  const [urlError, setUrlError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<CheckResult | null>(null);

  async function run(body: FormData, onError: string) {
    setBusy(true);
    setError(null);
    setResult(null);
    try {
      setResult(await apiFetch<CheckResult>("/api/check", { method: "POST", body }));
    } catch (e) {
      setError(e instanceof Error ? e.message : onError);
    } finally {
      setBusy(false);
    }
  }

  function submitUrl(e: React.FormEvent) {
    e.preventDefault();
    const value = url.trim();
    if (!value) {
      setUrlError("Paste the listing link or the image address.");
      return;
    }
    setUrlError(null);
    const fd = new FormData();
    fd.append("url", value);
    void run(fd, "Couldn't check that link");
  }

  function checkFile(file: File) {
    const fd = new FormData();
    fd.append("file", file);
    void run(fd, "Couldn't check that photo");
  }

  return (
    <AdaptiveChrome ground="ink">
      <div className="mx-auto max-w-3xl px-4 py-12 sm:px-6 sm:py-16">
        <FadeIn className="mb-10">
          <p className="kicker t-verify inline-flex items-center gap-2">
            <ScanSearch className="size-3.5" aria-hidden />
            Verify a listing
          </p>
          <h1 className="display-face mt-4 text-[clamp(1.875rem,4.5vw,2.75rem)]">
            Is this listing photo real?
          </h1>
          <p className="mt-5 max-w-2xl text-[16.5px] leading-relaxed text-muted-foreground">
            Looking at a listing somewhere else? Paste the link, or drop the photo. We recognise
            an OriginShot image even after a marketplace re-compressed it and stripped its record
            &mdash; and tell you what it actually is: AI-generated or authentic, by which model,
            and traceable back to the seller&apos;s original. Nothing you paste is stored.
          </p>
        </FadeIn>

        {/* ── The bench ──────────────────────────────────────────────────── */}
        <FadeIn>
          <section className="surface overflow-hidden rounded-xl border bg-card">
            <div className="flex flex-wrap items-baseline justify-between gap-x-6 gap-y-1 border-b px-5 py-3.5">
              <p className="kicker text-muted-foreground">Check a listing</p>
              <p className="kicker text-muted-foreground">link or photo</p>
            </div>

            {/* Primary: the link. It is what a buyer actually has in hand. */}
            <form
              onSubmit={submitUrl}
              className="p-5 sm:p-6"
              aria-describedby={urlError ? "url-error" : undefined}
            >
              <label
                htmlFor="url-input"
                className="kicker inline-flex items-center gap-2 text-muted-foreground"
              >
                <Link2 className="size-3.5" aria-hidden />
                Paste a listing or image link
              </label>
              <div className="mt-2.5 flex flex-col gap-2.5 sm:flex-row">
                <Input
                  id="url-input"
                  value={url}
                  onChange={(e) => {
                    setUrl(e.target.value);
                    if (urlError) setUrlError(null);
                  }}
                  placeholder="https://www.etsy.com/listing/…  or a direct image URL"
                  className="sm:flex-1"
                  inputMode="url"
                  aria-invalid={urlError ? true : undefined}
                  aria-describedby={urlError ? "url-error" : undefined}
                  autoComplete="off"
                  spellCheck={false}
                  disabled={busy}
                />
                <Button type="submit" variant="accent" className="sm:shrink-0" disabled={busy}>
                  Check it
                  <ArrowRight className="size-4" />
                </Button>
              </div>
              {urlError && (
                <p id="url-error" className="mt-2 text-xs text-danger">
                  {urlError}
                </p>
              )}
            </form>

            {/* The always-visible alternative, for surfaces that block hot-linking. */}
            <div className="border-t bg-muted/40 px-5 py-5 sm:px-6">
              <p className="kicker mb-2.5 text-muted-foreground">Or drop the photo</p>
              <UploadDropzone
                onFile={checkFile}
                busy={busy}
                title="Drop the listing photo"
                subtitle="Right-click the photo on the listing, save it, and drop it here"
                cta="Choose photo"
                accept="image/*"
                requireImage
              />
            </div>
          </section>
        </FadeIn>

        {/* ── The verdict ────────────────────────────────────────────────── */}
        {busy && (
          <div className="surface mt-4">
            <MediaSkeleton aspect="aspect-[3/1]" />
          </div>
        )}
        {error && (
          <div className="surface mt-4">
            <Alert title="Couldn't check that">{error}</Alert>
          </div>
        )}
        {result && (
          <FadeIn className="mt-4">
            <p className="kicker mb-2 px-1 text-muted-foreground">
              {SOURCE_NOTE[result.source](result.images_scanned)}
            </p>
            <div className="surface">
              <VerifyPanel result={result.result} />
            </div>
          </FadeIn>
        )}

        {/* ── Supporting, and clearly subordinate ────────────────────────── */}
        <div className="mt-14">
          <div className="kelvin-rule" aria-hidden />

          {/* Anyone checking a listing photo is usually already in an argument about it. */}
          <FadeIn className="mt-6">
            <Link
              href="/resolve"
              className="surface group flex items-start gap-3.5 rounded-xl border bg-card p-5 transition-colors hover:bg-secondary"
            >
              <Scale className="t-accent mt-0.5 size-4 shrink-0" aria-hidden />
              <span className="min-w-0 flex-1">
                <span className="block text-[14.5px] font-medium">
                  Already received something that doesn&apos;t match the listing?
                </span>
                <span className="mt-1 block text-[13.5px] leading-relaxed text-muted-foreground">
                  Resolve compares the item that arrived against the seller&apos;s authentic
                  original and issues a signed evidence report you can attach to a claim.
                </span>
              </span>
              <ArrowRight
                className="mt-0.5 size-4 shrink-0 text-muted-foreground transition-transform group-hover:translate-x-0.5"
                aria-hidden
              />
            </Link>
          </FadeIn>

          <p className="mt-6 px-1 text-[13px] leading-relaxed text-muted-foreground">
            A visual match is <em>evidence</em>, not a cryptographic signature: it means
            &ldquo;this is almost certainly that image&rdquo;, and the exact bit-distance is
            always shown so you can weigh it. If you have the untouched file straight from a
            seller,{" "}
            <Link href="/verify" className="t-accent underline-offset-2 hover:underline">
              verify it byte-for-byte
            </Link>{" "}
            instead.
          </p>
        </div>
      </div>
    </AdaptiveChrome>
  );
}
