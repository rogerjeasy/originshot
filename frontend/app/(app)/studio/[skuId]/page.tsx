"use client";

import { useEffect, useRef, useState } from "react";
import { useParams, useRouter } from "next/navigation";

import { ApiError, apiDownload, apiFetch } from "@/lib/api";
import { streamJob } from "@/lib/stream-job";
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
import { OrchestrationTrace } from "@/components/studio/orchestration-trace";
import { SkuSettings } from "@/components/studio/sku-settings";
import { UploadDropzone } from "@/components/upload-dropzone";
import { PageToolbar } from "@/components/workbench/page-toolbar";
import { RegistrationLabel } from "@/components/workbench/registration";
import { Section, Stack } from "@/components/workbench/section";
import { Alert } from "@/components/ui/alert";
import { MediaSkeleton } from "@/components/ui/skeleton";

export default function SkuWorkspace() {
  const { skuId } = useParams<{ skuId: string }>();
  const router = useRouter();
  const { data: sku, reload: reloadSku, setData: setSku } = useApiData<Sku>(`/api/skus/${skuId}`);
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
  // True from the moment Generate is clicked until the POST returns a job id. Without it the
  // button stays enabled and unchanged for the whole round-trip — which reads as "the click
  // did nothing", so the user clicks again and submits a *second* job with a second credit
  // hold. The request can take a while: generation runs inline, so an in-flight job's
  // blocking work delays every other request on the instance.
  const [submitting, setSubmitting] = useState(false);
  const doneStepsRef = useRef(0);
  const { refreshCredits } = useSession();

  const original = assets?.find((a) => a.is_authentic) ?? null;
  const generated = assets?.filter((a) => !a.is_authentic) ?? [];
  const busyJob = jobId !== null;
  // What the *controls* key off: a submit in flight is as busy as a job in flight, even
  // though no job id exists yet.
  const busy = submitting || busyJob;

  // Re-attach to a run this browser session didn't start. The job id lived in component state
  // only, so a refresh mid-generation left the page showing no progress for a SKU that was
  // very much still generating — and the server now refuses a second submit while that run is
  // live, so without this the user would be told a job is running with no way to watch it.
  useEffect(() => {
    let cancelled = false;
    apiFetch<Job | null>(`/api/skus/${skuId}/job`)
      .then((live) => {
        if (cancelled || !live) return;
        setJob(live);
        setJobId(live.id);
        doneStepsRef.current = live.steps?.filter((s) => s.status === "done").length ?? 0;
      })
      .catch(() => {
        /* best-effort: failing to find an existing run must not break the page */
      });
    return () => {
      cancelled = true;
    };
  }, [skuId]);

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
    // A second submit while the first is in flight would create a second job holding a
    // second estimate against the same balance. The button is disabled for the same
    // reason; this is the guard that holds when the click lands anyway.
    if (busy) return;
    setSubmitting(true);
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
    } finally {
      setSubmitting(false);
    }
  }

  // Replay re-runs one asset from its stored manifest — an ordinary job on the backend,
  // so it reuses the exact polling/progress machinery a generation does.
  async function replayAsset(a: Asset) {
    if (busy) return;   // same single-submit rule as generate() — a replay is an ordinary job
    setActive(null);
    setSubmitting(true);
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
    } finally {
      setSubmitting(false);
    }
  }

  // Watch the job while it runs — pushed via SSE, not polled. Keyed on the job *id* so the
  // watcher isn't torn down and rebuilt on every status update it itself causes.
  //
  // The stream is an optimisation over the 1.2s poll, never a dependency, and the poll is the
  // floor beneath it: whenever the stream stops — failed to establish, dropped, or simply
  // ended — polling takes over and runs until the job reaches a terminal status. The one rule
  // this watcher must never break is that it always resolves the UI, because the studio's
  // spinner and the server's stale-job reaper both depend on someone still reading the job.
  useEffect(() => {
    if (!jobId) return;
    let stopped = false;
    const controller = new AbortController();

    function handle(j: Job) {
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
        stopped = true;
        setJobId(null);
        if (j.status === "failed") setError(j.error ?? "Generation failed");
        void reloadAssets();
        // The hold has been settled against real provider cost — pull the true balance.
        void refreshCredits();
      }
    }

    /** Give up watching, but never silently: leave the user a resolved UI and a reason. */
    function abandon(reason: string) {
      stopped = true;
      setJobId(null);
      setError(reason);
      void reloadAssets();
    }

    async function poll() {
      let failures = 0;
      while (!stopped) {
        try {
          handle(await apiFetch<Job>(`/api/jobs/${jobId}`));
          failures = 0;
        } catch (e) {
          // A cold-starting or briefly-restarted instance must not kill the watcher —
          // giving up on the first hiccup is how a job ends up spinning forever with
          // nobody left to read (and therefore nobody left to reap) it.
          if (e instanceof ApiError && e.status === 404) {
            return abandon("This job no longer exists. Reload to see the SKU's assets.");
          }
          if (++failures >= 10) {
            return abandon(
              "Lost contact with the generation service. Reload to see this job's final state.",
            );
          }
        }
        if (stopped) return;
        await new Promise((r) => setTimeout(r, 1200));
      }
    }

    async function run() {
      try {
        await streamJob(jobId!, handle, controller.signal);
      } catch {
        /* stream unavailable: a buffering proxy, an older backend, a dropped connection */
      }
      // A stream can also end *cleanly* without ever carrying a terminal status — the server
      // caps one connection at _STREAM_MAX_SECONDS (api/generate.py) and any proxy in front
      // of it may close earlier. So "the stream ended" never means "the job finished", and
      // resolving must be treated exactly like throwing: keep watching by poll.
      //
      // Without this the watcher died silently on every job that outlived the stream cap:
      // the spinner ran forever, and because reaping happens on read (app/reaper.py), the
      // job was never failed and its credit hold was never refunded either.
      if (!stopped) await poll();
    }

    void run();
    return () => {
      stopped = true;
      controller.abort();
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
    <Stack gap="tight">
      <PageToolbar
        title={sku?.title ?? "Product"}
        crumbs={[{ label: "Studio", href: "/studio" }]}
        description={
          original
            ? generated.length > 0
              ? `${generated.length} generated asset${generated.length === 1 ? "" : "s"} from one source photo.`
              : "Pick styles on the right and generate your pack."
            : undefined
        }
        action={
          sku && !busy ? (
            <SkuSettings
              sku={sku}
              assetCount={generated.length}
              onSaved={(u) => setSku(u)}
              onDeleted={() => router.push("/studio")}
            />
          ) : undefined
        }
        meta={
          busy ? (
            <RegistrationLabel state="working">Generating</RegistrationLabel>
          ) : generated.length > 0 ? (
            <RegistrationLabel state="verified">Pack ready</RegistrationLabel>
          ) : undefined
        }
      />

      {error && (
        <FadeIn>
          <Alert title="Something went wrong">{error}</Alert>
        </FadeIn>
      )}

      <div className="grid gap-8 lg:grid-cols-[1fr_320px]">
        <div className="min-w-0 space-y-8">
          {/* "Still loading" and "no photo yet" are different states and must not render
              the same thing — treating them alike flashed the upload dropzone on every
              visit to a SKU that already has a photo. */}
          {assetsLoading && !assets ? (
            <Section label="Source photo">
              <div className="max-w-xs">
                <MediaSkeleton aspect="aspect-square" />
              </div>
            </Section>
          ) : !original ? (
            <Section
              label="Source photo"
              description="Everything in the pack is generated from this one image, and stays bound to it."
            >
              <UploadDropzone onFile={upload} busy={uploading} />
            </Section>
          ) : (
            <FadeIn>
              <Section label="Source photo" state="verified">
                <div className="max-w-xs">
                  <ImageTile asset={original} onClick={() => setActive(original)} />
                </div>
              </Section>
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

          {/* The run as an orchestration — provider + modality per step — once it has finished.
              Answers "Use of Genblaze" at a glance: which providers, which modalities, in one
              pipeline. Stays mounted after completion so it's there to read (and screenshot). */}
          {job && !busy && <OrchestrationTrace job={job} />}

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

        <FadeIn delay={0.08} className="space-y-8 lg:sticky lg:top-20 lg:self-start">
          <GeneratePanel
            styles={styles}
            onStylesChange={setStyles}
            marketplaces={marketplaces}
            onMarketplacesChange={setMarketplaces}
            hasOriginal={Boolean(original)}
            busy={busy}
            onGenerate={generate}
            canExport={generated.length > 0}
            onExport={exportPack}
            exporting={exporting}
            job={job}
          />
          {original && !busy && (
            <CompliancePanel skuId={skuId} refreshKey={assets?.length ?? 0} />
          )}
        </FadeIn>
      </div>

      <Lightbox
        asset={active}
        onClose={() => setActive(null)}
        onReplay={replayAsset}
        replayDisabled={busy}
      />
    </Stack>
  );
}
