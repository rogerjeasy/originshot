"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import {
  AlertTriangle,
  ArrowLeft,
  Check,
  Download,
  Layers,
  Loader2,
  Sparkles,
  X,
} from "lucide-react";

import { apiDownload, apiFetch } from "@/lib/api";
import { useSession } from "@/lib/use-session";
import { cn } from "@/lib/utils";
import type { Batch, BatchEstimate, Marketplace, Sku, Style } from "@/lib/types";
import { CatalogBoard } from "@/components/studio/catalog-board";
import { FadeIn } from "@/components/motion/fade-in";
import { MarketplacePicker } from "@/components/marketplace-picker";
import { PageHeader } from "@/components/page-header";
import { StylePicker } from "@/components/style-picker";
import { UploadDropzone } from "@/components/upload-dropzone";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

type StagedStatus = "staged" | "uploading" | "ready" | "failed";

interface Staged {
  id: string;
  file: File;
  title: string;
  status: StagedStatus;
  skuId?: string;
  error?: string;
}

/** "IMG_4821 mug-front.JPG" → "Mug front" — a usable default the seller can overwrite. */
function titleFromFilename(name: string): string {
  const stem = name.replace(/\.[^.]+$/, "");
  const cleaned = stem
    .replace(/[_-]+/g, " ")
    .replace(/\b(img|dsc|photo|image)[\s]*\d+\b/gi, "")
    .replace(/\s+/g, " ")
    .trim();
  const usable = cleaned || stem;
  return usable.charAt(0).toUpperCase() + usable.slice(1);
}

function formatEta(seconds: number): string {
  if (seconds < 90) return `${Math.round(seconds)}s`;
  return `${Math.round(seconds / 60)} min`;
}

/**
 * Catalog Mode — many products, one run.
 *
 * Three phases on one page, because they are one intent: stage the photos, see what the run
 * will cost, watch it happen. Uploads go through the ordinary per-SKU routes one file at a
 * time (see app/api/batches.py for why), so this page owns the fan-out and can show real
 * per-file progress instead of one opaque bar.
 */
export default function CatalogPage() {
  const { refreshCredits } = useSession();
  const [staged, setStaged] = useState<Staged[]>([]);
  const [styles, setStyles] = useState<Style[]>(["studio", "lifestyle"]);
  const [marketplaces, setMarketplaces] = useState<Marketplace[]>(["amazon"]);
  const [estimate, setEstimate] = useState<BatchEstimate | null>(null);
  const [batch, setBatch] = useState<Batch | null>(null);
  const [uploading, setUploading] = useState(false);
  const [starting, setStarting] = useState(false);
  const [exporting, setExporting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const readyIds = staged.filter((s) => s.status === "ready" && s.skuId).map((s) => s.skuId!);
  const batchIdRef = useRef<string | null>(null);
  batchIdRef.current = batch?.id ?? null;
  const live = batch?.status === "queued" || batch?.status === "running";

  function addFiles(files: File[]) {
    setError(null);
    setStaged((prev) => [
      ...prev,
      ...files.map((file, i) => ({
        id: `${Date.now()}-${i}-${file.name}`,
        file,
        title: titleFromFilename(file.name),
        status: "staged" as const,
      })),
    ]);
  }

  function patch(id: string, fields: Partial<Staged>) {
    setStaged((prev) => prev.map((s) => (s.id === id ? { ...s, ...fields } : s)));
  }

  /** Create a SKU per photo and upload it. Sequential on purpose — see below. */
  async function uploadAll() {
    setUploading(true);
    setError(null);
    const pending = staged.filter((s) => s.status === "staged" || s.status === "failed");
    for (const item of pending) {
      patch(item.id, { status: "uploading", error: undefined });
      try {
        const sku = await apiFetch<Sku>("/api/skus", {
          method: "POST",
          body: JSON.stringify({ title: item.title.trim() || item.file.name }),
        });
        const fd = new FormData();
        fd.append("file", item.file);
        await apiFetch(`/api/skus/${sku.id}/upload`, { method: "POST", body: fd });
        patch(item.id, { status: "ready", skuId: sku.id });
      } catch (e) {
        // One bad photo must not abandon the rest of the catalog — record it and continue.
        patch(item.id, {
          status: "failed",
          error: e instanceof Error ? e.message : "Upload failed",
        });
      }
    }
    setUploading(false);
  }

  const quote = useCallback(async () => {
    if (!readyIds.length) {
      setEstimate(null);
      return;
    }
    try {
      setEstimate(
        await apiFetch<BatchEstimate>("/api/batches/estimate", {
          method: "POST",
          body: JSON.stringify({ sku_ids: readyIds, styles, marketplaces }),
        }),
      );
    } catch {
      setEstimate(null); // a failed quote must not block the run; the server re-checks
    }
    // readyIds is derived from `staged`; depending on its identity would re-quote every render.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [staged, styles, marketplaces]);

  useEffect(() => {
    void quote();
  }, [quote]);

  async function start() {
    if (!readyIds.length) return;
    setStarting(true);
    setError(null);
    try {
      setBatch(
        await apiFetch<Batch>("/api/batches", {
          method: "POST",
          body: JSON.stringify({ sku_ids: readyIds, styles, marketplaces }),
        }),
      );
    } catch (e) {
      setError(e instanceof Error ? e.message : "Couldn't start the catalog run");
    } finally {
      setStarting(false);
    }
  }

  // Poll while the run is live. Keyed on the id (not the object) so the interval isn't torn
  // down and rebuilt by every update the poll itself causes.
  useEffect(() => {
    if (!live || !batch?.id) return;
    const id = batch.id;
    const t = setInterval(async () => {
      try {
        const next = await apiFetch<Batch>(`/api/batches/${id}`);
        if (batchIdRef.current !== id) return;
        setBatch(next);
        if (next.status !== "queued" && next.status !== "running") {
          clearInterval(t);
          await refreshCredits();
        }
      } catch {
        clearInterval(t);
      }
    }, 1500);
    return () => clearInterval(t);
  }, [live, batch?.id, refreshCredits]);

  async function downloadCatalog() {
    if (!batch) return;
    setExporting(true);
    setError(null);
    try {
      const { blob, filename } = await apiDownload(`/api/batches/${batch.id}/export`, {
        method: "POST",
        body: JSON.stringify({ marketplaces }),
      });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = filename ?? `originshot-catalog-${batch.id.slice(0, 8)}.zip`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Export failed");
    } finally {
      setExporting(false);
    }
  }

  const needsUpload = staged.some((s) => s.status === "staged" || s.status === "failed");

  return (
    <div className="space-y-8">
      <PageHeader
        title="Catalog Mode"
        description="Drop a folder of product photos and generate the whole shop in one run."
        action={
          <Link
            href="/studio"
            className="inline-flex items-center gap-1.5 text-sm text-muted-foreground transition-colors hover:text-foreground"
          >
            <ArrowLeft className="size-4" /> Back to Studio
          </Link>
        }
      />

      {!batch && (
        <>
          <FadeIn>
            <UploadDropzone
              onFiles={addFiles}
              busy={uploading}
              title="Drop your product photos"
              subtitle="One product per photo · PNG / JPG / WebP · EXIF stripped on upload"
              cta="Choose photos"
            />
          </FadeIn>

          {staged.length > 0 && (
            <FadeIn>
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <Layers className="size-4 t-accent" />
                    {staged.length} product{staged.length === 1 ? "" : "s"} staged
                  </CardTitle>
                </CardHeader>
                <CardContent className="space-y-3">
                  <ul className="divide-y">
                    {staged.map((item) => (
                      <li key={item.id} className="flex items-center gap-3 py-2.5">
                        <span
                          className={cn(
                            "grid size-6 shrink-0 place-items-center rounded-full border",
                            item.status === "ready" &&
                              "border-transparent bg-verified/12 text-verified",
                            item.status === "uploading" &&
                              "border-transparent bg-accent/12 t-accent",
                            item.status === "failed" &&
                              "border-transparent bg-danger/12 text-danger",
                            item.status === "staged" && "text-muted-foreground",
                          )}
                        >
                          {item.status === "ready" ? (
                            <Check className="size-3.5" />
                          ) : item.status === "uploading" ? (
                            <Loader2 className="size-3.5 animate-spin" />
                          ) : item.status === "failed" ? (
                            <AlertTriangle className="size-3.5" />
                          ) : (
                            <span className="size-1.5 rounded-full bg-current" />
                          )}
                        </span>

                        <div className="min-w-0 flex-1">
                          <input
                            value={item.title}
                            onChange={(e) => patch(item.id, { title: e.target.value })}
                            disabled={item.status !== "staged"}
                            aria-label={`Title for ${item.file.name}`}
                            className="w-full truncate border-0 bg-transparent p-0 text-sm font-medium outline-none focus:ring-0 disabled:text-muted-foreground"
                          />
                          <p className="truncate font-mono text-[11px] text-muted-foreground">
                            {item.file.name} · {(item.file.size / 1024).toFixed(0)} KB
                          </p>
                          {item.error && (
                            <p className="mt-0.5 text-xs text-danger">{item.error}</p>
                          )}
                        </div>

                        {item.status === "staged" && (
                          <button
                            type="button"
                            onClick={() =>
                              setStaged((prev) => prev.filter((s) => s.id !== item.id))
                            }
                            aria-label={`Remove ${item.title}`}
                            className="grid size-6 shrink-0 place-items-center rounded text-muted-foreground transition-colors hover:bg-secondary hover:text-foreground"
                          >
                            <X className="size-3.5" />
                          </button>
                        )}
                      </li>
                    ))}
                  </ul>

                  {needsUpload && (
                    <Button onClick={uploadAll} disabled={uploading} variant="outline">
                      {uploading ? <Loader2 className="animate-spin" /> : null}
                      Upload {staged.filter((s) => s.status !== "ready").length} photo
                      {staged.filter((s) => s.status !== "ready").length === 1 ? "" : "s"}
                    </Button>
                  )}
                </CardContent>
              </Card>
            </FadeIn>
          )}

          {readyIds.length > 0 && (
            <FadeIn>
              <Card>
                <CardHeader>
                  <CardTitle>What to generate</CardTitle>
                </CardHeader>
                <CardContent className="space-y-5">
                  <div className="space-y-2">
                    <p className="label text-muted-foreground">Styles · per product</p>
                    <StylePicker value={styles} onChange={setStyles} />
                  </div>
                  <div className="space-y-2">
                    <p className="label text-muted-foreground">Marketplace formats</p>
                    <MarketplacePicker value={marketplaces} onChange={setMarketplaces} />
                  </div>

                  {estimate && (
                    <dl className="divide-y rounded-md border">
                      <div className="flex items-baseline justify-between px-3 py-2">
                        <dt className="label text-muted-foreground">Products</dt>
                        <dd className="tabular font-mono text-sm">{estimate.skus}</dd>
                      </div>
                      <div className="flex items-baseline justify-between px-3 py-2">
                        <dt className="label text-muted-foreground">Per product</dt>
                        <dd className="tabular font-mono text-sm">
                          ${estimate.per_sku_usd.toFixed(2)}
                        </dd>
                      </div>
                      <div className="flex items-baseline justify-between px-3 py-2">
                        <dt className="label text-muted-foreground">Estimated total</dt>
                        <dd className="tabular font-mono text-sm font-medium">
                          ${estimate.total_estimate_usd.toFixed(2)}
                        </dd>
                      </div>
                      <div className="flex items-baseline justify-between px-3 py-2">
                        <dt className="label text-muted-foreground">Approx. time</dt>
                        <dd className="tabular font-mono text-sm">
                          {formatEta(estimate.eta_seconds)}
                        </dd>
                      </div>
                    </dl>
                  )}

                  {estimate && !estimate.affordable && (
                    <Alert variant="warning" title="Not enough credit for this catalog">
                      This run needs ${estimate.total_estimate_usd.toFixed(2)} but your
                      balance is ${estimate.balance_usd.toFixed(2)}. Remove some products or
                      ask an admin to top up.
                    </Alert>
                  )}
                  {estimate && estimate.quota_remaining < estimate.skus && (
                    <Alert variant="warning" title="Daily quota is lower than this catalog">
                      {estimate.quota_remaining} generation
                      {estimate.quota_remaining === 1 ? "" : "s"} left today. The rest will be
                      marked not started — they cost nothing and can be re-run tomorrow.
                    </Alert>
                  )}

                  <Button
                    variant="accent"
                    onClick={start}
                    disabled={starting || !styles.length || (estimate ? !estimate.affordable : false)}
                  >
                    {starting ? <Loader2 className="animate-spin" /> : <Sparkles />}
                    Generate {readyIds.length} product{readyIds.length === 1 ? "" : "s"}
                  </Button>
                </CardContent>
              </Card>
            </FadeIn>
          )}
        </>
      )}

      {batch && (
        <FadeIn className="space-y-4">
          <CatalogBoard batch={batch} />
          {!live && (
            <div className="flex flex-wrap gap-3">
              <Button variant="accent" onClick={downloadCatalog} disabled={exporting}>
                {exporting ? <Loader2 className="animate-spin" /> : <Download />}
                Download the whole catalog
              </Button>
              <Button
                variant="outline"
                onClick={() => {
                  setBatch(null);
                  setStaged([]);
                  setEstimate(null);
                }}
              >
                Start another
              </Button>
            </div>
          )}
        </FadeIn>
      )}

      {error && <Alert title="Something went wrong">{error}</Alert>}
    </div>
  );
}
