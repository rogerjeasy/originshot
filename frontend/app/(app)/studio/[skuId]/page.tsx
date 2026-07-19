"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { ArrowLeft } from "lucide-react";

import { apiDownload, apiFetch } from "@/lib/api";
import { useApiData } from "@/lib/use-api";
import { useSession } from "@/lib/use-session";
import type { Asset, Job, Marketplace, Sku, Style } from "@/lib/types";
import { FadeIn } from "@/components/motion/fade-in";
import { ImageTile } from "@/components/image-tile";
import { Lightbox } from "@/components/lightbox";
import { AssetWorkbench } from "@/components/studio/asset-workbench";
import { JobProgress } from "@/components/studio/job-progress";
import { CompliancePanel } from "@/components/studio/compliance-panel";
import { GeneratePanel } from "@/components/studio/generate-panel";
import { LineageGraph } from "@/components/studio/lineage-graph";
import { ListingPanel } from "@/components/studio/listing-panel";
import { UploadDropzone } from "@/components/upload-dropzone";
import { Alert } from "@/components/ui/alert";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { MediaSkeleton } from "@/components/ui/skeleton";

export default function SkuWorkspace() {
  const { skuId } = useParams<{ skuId: string }>();
  const { data: sku, reload: reloadSku } = useApiData<Sku>(`/api/skus/${skuId}`);
  const {
    data: assets,
    loading: assetsLoading,
    reload: reloadAssets,
  } = useApiData<Asset[]>(`/api/skus/${skuId}/assets`);

  const [styles, setStyles] = useState<Style[]>(["studio", "lifestyle"]);
  const [marketplaces, setMarketplaces] = useState<Marketplace[]>([]);
  const [uploading, setUploading] = useState(false);
  const [exporting, setExporting] = useState(false);
  const [job, setJob] = useState<Job | null>(null);
  const [jobId, setJobId] = useState<string | null>(null);
  const [active, setActive] = useState<Asset | null>(null);
  const [error, setError] = useState<string | null>(null);
  const doneStepsRef = useRef(0);
  const { refreshCredits } = useSession();

  const original = assets?.find((a) => a.is_authentic) ?? null;
  const generated = assets?.filter((a) => !a.is_authentic) ?? [];
  const busyJob = jobId !== null;

  // Styles whose step is queued or running, so the workbench can hold a slot
  // open for each frame that's still on its way.
  const pendingStyles =
    job?.steps
      ?.filter((s) => s.status === "pending" || s.status === "running")
      .map((s) => s.style) ?? [];

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
    doneStepsRef.current = 0;
    try {
      const j = await apiFetch<Job>(`/api/skus/${skuId}/generate`, {
        method: "POST",
        body: JSON.stringify({ styles, marketplaces }),
      });
      setJob(j);
      setJobId(j.id);
      // The estimate has just been held, so the visible balance is already out of date.
      void refreshCredits();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Generation failed");
    }
  }

  // Replay re-runs one asset from its stored manifest — an ordinary job on the backend,
  // so it reuses the exact polling/progress machinery a generation does.
  async function replayAsset(a: Asset) {
    setActive(null);
    setError(null);
    doneStepsRef.current = 0;
    try {
      const j = await apiFetch<Job>(`/api/skus/${skuId}/assets/${a.id}/replay`, {
        method: "POST",
      });
      setJob(j);
      setJobId(j.id);
      void refreshCredits();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Replay failed");
    }
  }

  // Poll the job while it runs. Polls on the job *id* (not the job object) so a new
  // interval isn't torn down and rebuilt on every status update the poll itself causes.
  useEffect(() => {
    if (!jobId) return;
    let stopped = false;

    const t = setInterval(async () => {
      try {
        const j = await apiFetch<Job>(`/api/jobs/${jobId}`);
        if (stopped) return;
        setJob(j);

        // Assets land step by step, so refresh the grid whenever the completed-step count
        // moves — the user sees each image as it finishes instead of all of them at the end.
        const done = j.steps?.filter((s) => s.status === "done").length ?? 0;
        if (done !== doneStepsRef.current) {
          doneStepsRef.current = done;
          void reloadAssets();
        }

        if (j.status === "done" || j.status === "failed" || j.status === "partial") {
          clearInterval(t);
          setJobId(null);
          if (j.status === "failed") setError(j.error ?? "Generation failed");
          await reloadAssets();
          // The hold has been settled against real provider cost — pull the true balance.
          await refreshCredits();
        }
      } catch {
        clearInterval(t);
        setJobId(null);
      }
    }, 1200);

    return () => {
      stopped = true;
      clearInterval(t);
    };
  }, [jobId, reloadAssets, refreshCredits]);

  async function exportPack() {
    setError(null);
    setExporting(true);
    try {
      // The export is a ZIP (marketplace renditions + verifiable masters + manifests),
      // so take the raw blob — never stringify it.
      const { blob, filename } = await apiDownload(`/api/skus/${skuId}/export`, {
        method: "POST",
        body: JSON.stringify({ marketplaces }),
      });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = filename ?? `OriginShot-${skuId}.zip`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Export failed");
    } finally {
      setExporting(false);
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
          {/* "Still loading" and "no photo yet" are different states and must not render
              the same thing — treating them alike flashed the upload dropzone on every
              visit to a SKU that already has a photo. */}
          {assetsLoading && !assets ? (
            <Card>
              <CardHeader>
                <CardTitle>Original</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="max-w-xs">
                  <MediaSkeleton aspect="aspect-square" />
                </div>
              </CardContent>
            </Card>
          ) : !original ? (
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

          {/* Progress stays mounted after the run so the finished timings remain readable
              instead of vanishing the moment the last step lands. */}
          {job && <JobProgress job={job} />}

          {(generated.length > 0 || pendingStyles.length > 0) && (
            <AssetWorkbench
              assets={generated}
              pendingStyles={pendingStyles}
              onSelect={setActive}
            />
          )}

          {assets && assets.length > 1 && (
            <FadeIn>
              <LineageGraph assets={assets} />
            </FadeIn>
          )}

          {sku && (
            <FadeIn>
              <ListingPanel skuId={skuId} marketplaces={marketplaces} />
            </FadeIn>
          )}
        </div>

        <FadeIn delay={0.08} className="space-y-6 lg:sticky lg:top-20 lg:self-start">
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
            exporting={exporting}
            job={job}
          />
          {original && !busyJob && (
            <CompliancePanel skuId={skuId} refreshKey={assets?.length ?? 0} />
          )}
        </FadeIn>
      </div>

      <Lightbox
        asset={active}
        onClose={() => setActive(null)}
        onReplay={replayAsset}
        replayDisabled={busyJob}
      />
    </div>
  );
}
