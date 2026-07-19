"use client";

import { useState } from "react";
import { Scale } from "lucide-react";

import { apiFetch } from "@/lib/api";
import type { ResolveReport } from "@/lib/types";
import { AdaptiveChrome } from "@/components/adaptive-chrome";
import { FadeIn } from "@/components/motion/fade-in";
import { ResolvePanel } from "@/components/resolve-panel";
import { UploadDropzone } from "@/components/upload-dropzone";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { MediaSkeleton } from "@/components/ui/skeleton";

/**
 * Resolve — the buyer's and the marketplace's entry point.
 *
 * Deliberately public and account-free: the people who need this are on the other side of
 * the transaction from the seller who generated the images. Two inputs, stated in the order
 * a dispute actually arrives in — "here's what was advertised", "here's what turned up".
 */
export default function ResolveHome() {
  const [listing, setListing] = useState<File | null>(null);
  const [received, setReceived] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [report, setReport] = useState<ResolveReport | null>(null);

  async function submit() {
    if (!listing) return;
    setBusy(true);
    setError(null);
    setReport(null);
    try {
      const fd = new FormData();
      fd.append("listing_file", listing);
      if (received) fd.append("received_file", received);
      setReport(await apiFetch<ResolveReport>("/api/resolve", { method: "POST", body: fd }));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Couldn't produce a report");
    } finally {
      setBusy(false);
    }
  }

  return (
    <AdaptiveChrome>
      <div className="mx-auto max-w-2xl px-4 py-12 sm:px-6 sm:py-16">
        <FadeIn className="mb-8">
          <span className="grid size-11 place-items-center rounded-md border bg-card text-accent shadow-raised">
            <Scale className="size-5" />
          </span>
          <h1 className="mt-5 text-3xl font-semibold tracking-[-0.03em]">
            Resolve a dispute
          </h1>
          <p className="mt-3 text-muted-foreground">
            Two questions, answered together: was the listing photo honest about how it was
            made, and is the item that arrived the item it depicts? You don&apos;t need an
            account — this is for whoever is holding the parcel.
          </p>
        </FadeIn>

        <FadeIn className="space-y-6">
          <section className="space-y-3">
            <div>
              <p className="label text-muted-foreground">Step 1 · required</p>
              <h2 className="mt-1 font-semibold tracking-tight">The listing image</h2>
              <p className="mt-1 text-sm text-muted-foreground">
                The photo from the listing. Its provenance is re-derived from the bytes you
                supply — we never take our own database&apos;s word for it.
              </p>
            </div>
            <UploadDropzone
              onFile={(f) => {
                setListing(f);
                setReport(null);
              }}
              title={listing ? listing.name : "Drop the listing image"}
              subtitle={
                listing
                  ? "Loaded — drop another to replace it"
                  : "PNG / JPG / WebP · nothing is kept"
              }
              cta={listing ? "Replace" : "Choose file"}
            />
          </section>

          <section className="space-y-3">
            <div>
              <p className="label text-muted-foreground">Step 2 · optional</p>
              <h2 className="mt-1 font-semibold tracking-tight">
                A photo of what actually arrived
              </h2>
              <p className="mt-1 text-sm text-muted-foreground">
                Compared against the seller&apos;s authentic original — the photo taken
                before any AI processing, not the marketing shot. A phone snap is fine.
                This image is never stored; only its hash goes in the report.
              </p>
            </div>
            <UploadDropzone
              onFile={(f) => {
                setReceived(f);
                setReport(null);
              }}
              title={received ? received.name : "Drop a photo of the delivered item"}
              subtitle={
                received
                  ? "Loaded — drop another to replace it"
                  : "Skip this to check the listing image's provenance alone"
              }
              cta={received ? "Replace" : "Choose file"}
            />
          </section>

          <div className="flex flex-wrap items-center gap-3">
            <Button variant="accent" onClick={submit} disabled={!listing || busy}>
              {busy ? "Examining…" : "Produce evidence report"}
            </Button>
            {!listing && (
              <p className="text-sm text-muted-foreground">
                A listing image is required to start.
              </p>
            )}
          </div>

          {busy && <MediaSkeleton aspect="aspect-[3/1]" />}
          {error && <Alert title="Couldn't produce a report">{error}</Alert>}
          {report && (
            <FadeIn>
              <ResolvePanel report={report} />
            </FadeIn>
          )}
        </FadeIn>
      </div>
    </AdaptiveChrome>
  );
}
