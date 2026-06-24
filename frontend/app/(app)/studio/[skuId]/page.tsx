"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { ArrowLeft } from "lucide-react";

import { apiFetch } from "@/lib/api";
import { useApiData } from "@/lib/use-api";
import type { Asset, Job, Marketplace, Sku, Style } from "@/lib/types";
import { FadeIn } from "@/components/motion/fade-in";
import { Stagger, StaggerItem } from "@/components/motion/stagger";
import { ImageTile } from "@/components/image-tile";
import { Lightbox } from "@/components/lightbox";
import { DevelopingGrid } from "@/components/studio/developing-grid";
import { GeneratePanel } from "@/components/studio/generate-panel";
import { UploadDropzone } from "@/components/upload-dropzone";
import { Alert } from "@/components/ui/alert";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export default function SkuWorkspace() {
  const { skuId } = useParams<{ skuId: string }>();
  const { data: sku, reload: reloadSku } = useApiData<Sku>(`/api/skus/${skuId}`);
  const { data: assets, reload: reloadAssets } = useApiData<Asset[]>(`/api/skus/${skuId}/assets`);

  const [styles, setStyles] = useState<Style[]>(["studio", "lifestyle"]);
  const [marketplaces, setMarketplaces] = useState<Marketplace[]>([]);
  const [uploading, setUploading] = useState(false);
  const [job, setJob] = useState<Job | null>(null);
  const [active, setActive] = useState<Asset | null>(null);
  const [error, setError] = useState<string | null>(null);

  const original = assets?.find((a) => a.is_authentic) ?? null;
  const generated = assets?.filter((a) => !a.is_authentic) ?? [];
  const busyJob = job !== null && job.status !== "done" && job.status !== "failed";

  async function upload(file: File) {
    setUploading(true);
    setError(null);
    try {
      const fd = new FormData();
      fd.append("file", file);
      await apiFetch(`/api/skus/${skuId}/upload`, { method: "POST", body: fd });
      await Promise.all([reloadSku(), reloadAssets()]);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Upload failed");
    } finally {
      setUploading(false);
    }
  }

  async function generate() {
    setError(null);
    try {
      const j = await apiFetch<Job>(`/api/skus/${skuId}/generate`, {
        method: "POST",
        body: JSON.stringify({ styles, marketplaces }),
      });
      setJob(j);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Generation failed");
    }
  }

  useEffect(() => {
    if (!job || job.status === "done" || job.status === "failed") return;
    const t = setInterval(async () => {
      try {
        const j = await apiFetch<Job>(`/api/jobs/${job.id}`);
        setJob(j);
        if (j.status === "done" || j.status === "failed") {
          clearInterval(t);
          if (j.status === "failed") setError(j.error ?? "Generation failed");
          await reloadAssets();
        }
      } catch {
        clearInterval(t);
      }
    }, 1500);
    return () => clearInterval(t);
  }, [job, reloadAssets]);

  async function exportPack() {
    setError(null);
    try {
      const data = await apiFetch(`/api/skus/${skuId}/export`, {
        method: "POST",
        body: JSON.stringify({ marketplaces }),
      });
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `${skuId}-export.json`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Export failed");
    }
  }

  return (
    <div className="space-y-8">
      <div className="flex items-center gap-3">
        <Link
          href="/studio"
          className="lift inline-grid size-9 place-items-center rounded-lg border bg-card text-muted-foreground hover:text-foreground"
          aria-label="Back to Studio"
        >
          <ArrowLeft className="size-4" />
        </Link>
        <div className="min-w-0">
          <h1 className="min-w-0 truncate text-2xl font-semibold tracking-tight">
            {sku?.title ?? "Product"}
          </h1>
          {original && (
            <p className="text-sm text-muted-foreground">
              {generated.length > 0
                ? `${generated.length} generated asset${generated.length === 1 ? "" : "s"}`
                : "Pick styles and generate your pack"}
            </p>
          )}
        </div>
      </div>

      {error && (
        <FadeIn>
          <Alert>{error}</Alert>
        </FadeIn>
      )}

      <div className="grid gap-6 lg:grid-cols-[1fr_320px]">
        <div className="min-w-0 space-y-6">
          {!original ? (
            <UploadDropzone onFile={upload} busy={uploading} />
          ) : (
            <FadeIn>
              <Card>
                <CardHeader>
                  <CardTitle>Original</CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="max-w-xs">
                    <ImageTile asset={original} onClick={() => setActive(original)} />
                  </div>
                </CardContent>
              </Card>
            </FadeIn>
          )}

          {busyJob ? (
            <DevelopingGrid styles={job!.requested_styles} />
          ) : generated.length > 0 ? (
            <section>
              <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-muted-foreground">
                Generated pack
              </h2>
              <Stagger className="grid grid-cols-2 gap-4 sm:grid-cols-3 xl:grid-cols-4">
                {generated.map((a) => (
                  <StaggerItem key={a.id}>
                    <ImageTile asset={a} onClick={() => setActive(a)} />
                  </StaggerItem>
                ))}
              </Stagger>
            </section>
          ) : null}
        </div>

        <FadeIn delay={0.08} className="lg:sticky lg:top-20 lg:self-start">
          <GeneratePanel
            styles={styles}
            onStylesChange={setStyles}
            marketplaces={marketplaces}
            onMarketplacesChange={setMarketplaces}
            hasOriginal={Boolean(original)}
            busy={busyJob}
            onGenerate={generate}
            canExport={generated.length > 0}
            onExport={exportPack}
            job={job}
          />
        </FadeIn>
      </div>

      <Lightbox asset={active} onClose={() => setActive(null)} />
    </div>
  );
}
