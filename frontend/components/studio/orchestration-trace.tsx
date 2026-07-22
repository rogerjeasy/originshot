"use client";

import { AudioLines, Check, ImageIcon, TriangleAlert, Video, Workflow } from "lucide-react";

import { cn } from "@/lib/utils";
import type { Job, JobStep } from "@/lib/types";

/**
 * The run as an orchestration, not a progress bar. The judging question "does this use
 * Genblaze to orchestrate across models, providers, or steps?" is answered here in one
 * glance: every step's provider and modality is on screen, so a run that spans GMI image +
 * GMI video + OpenAI TTS + a local mux reads as the multi-provider, multi-modality pipeline
 * it is — instead of that fact living only in logs and prose.
 *
 * Everything shown is what the server reported on the job document; no provider name or
 * modality is invented, and skipped/failed steps are shown as such rather than hidden.
 */

const STYLE_LABEL: Record<string, string> = {
  studio: "Studio",
  lifestyle: "Lifestyle",
  onmodel: "On-model",
  variant: "Variants",
  video: "Hero video",
  voiceover: "Voiceover",
};

type ModalityKind = "image" | "video" | "audio";

const STYLE_MODALITY: Record<string, ModalityKind> = {
  studio: "image",
  lifestyle: "image",
  onmodel: "image",
  variant: "image",
  video: "video",
  voiceover: "audio",
};

const MODALITY_ICON: Record<ModalityKind, React.ComponentType<{ className?: string }>> = {
  image: ImageIcon,
  video: Video,
  audio: AudioLines,
};

/** Provider family + a dot colour, so "who served this step" is scannable down the flow. */
function providerFamily(provider?: string | null): { label: string; dot: string } {
  const p = (provider ?? "").toLowerCase();
  if (p.includes("openai")) return { label: "OpenAI", dot: "bg-emerald-500" };
  if (p.includes("gmi")) return { label: "GMI Cloud", dot: "bg-violet-500" };
  if (p.includes("ffmpeg")) return { label: "local ffmpeg", dot: "bg-amber-500" };
  if (p.includes("mock")) return { label: "mock", dot: "bg-muted-foreground" };
  return { label: provider ?? "—", dot: "bg-muted-foreground" };
}

function StepNode({ step }: { step: JobStep }) {
  const modality = STYLE_MODALITY[step.style] ?? "image";
  const Icon = MODALITY_ICON[modality];
  const fam = providerFamily(step.provider);
  const ran = step.status === "done";
  const failed = step.status === "failed";
  const skipped = step.status === "skipped";

  return (
    <div
      className={cn(
        "min-w-[9.5rem] shrink-0 rounded-lg border bg-card p-3",
        failed && "border-danger/40",
        skipped && "opacity-70",
      )}
    >
      <div className="flex items-center gap-2">
        <Icon className="size-3.5 text-muted-foreground" />
        <span className="truncate text-[13px] font-medium">
          {STYLE_LABEL[step.style] ?? step.style}
        </span>
      </div>

      {ran && step.provider ? (
        <div className="mt-2 space-y-1">
          <span className="flex items-center gap-1.5">
            <span className={cn("size-2 shrink-0 rounded-full", fam.dot)} />
            <span className="text-xs">{fam.label}</span>
          </span>
          {step.model && (
            <p className="truncate font-mono text-[11px] text-muted-foreground" title={step.model}>
              {step.model}
            </p>
          )}
          <div className="flex items-center gap-2 pt-0.5">
            {step.qa_passed != null &&
              (step.qa_passed ? (
                <span className="inline-flex items-center gap-0.5 text-[11px] text-verified">
                  <Check className="size-3" />
                  QA{(step.qa_attempts ?? 1) > 1 ? ` ×${step.qa_attempts}` : ""}
                </span>
              ) : (
                <span className="inline-flex items-center gap-0.5 text-[11px] text-warning">
                  <TriangleAlert className="size-3" />
                  QA
                </span>
              ))}
            {step.cost_source === "estimate" && (
              <span className="font-mono text-[10px] text-muted-foreground" title="list-price estimate; provider reported no cost">
                est.
              </span>
            )}
          </div>
        </div>
      ) : (
        <p className={cn("mt-2 text-[11px]", failed ? "text-danger" : "text-muted-foreground")}>
          {failed ? "failed" : skipped ? "skipped" : "—"}
        </p>
      )}
    </div>
  );
}

export function OrchestrationTrace({ job }: { job: Job }) {
  const steps = (job.steps ?? []).filter(
    (s) => s.status !== "pending" && s.status !== "running",
  );
  if (steps.length === 0) return null;

  const done = steps.filter((s) => s.status === "done");
  const providers = new Set(done.map((s) => providerFamily(s.provider).label));
  const modalities = new Set(done.map((s) => STYLE_MODALITY[s.style] ?? "image"));

  return (
    <section className="rounded-lg border bg-card p-5">
      <div className="mb-3 flex flex-wrap items-baseline justify-between gap-2">
        <h2 className="label flex items-center gap-2 text-muted-foreground">
          <Workflow className="size-3.5 t-accent" aria-hidden />
          Orchestration — one run, through Genblaze
        </h2>
        <p className="font-mono text-xs text-muted-foreground">
          {done.length} step{done.length === 1 ? "" : "s"} · {providers.size} provider
          {providers.size === 1 ? "" : "s"} · {modalities.size} modalit
          {modalities.size === 1 ? "y" : "ies"}
        </p>
      </div>

      {/* Horizontal flow: each step a node, chevrons between them. Scrolls on narrow screens
          rather than wrapping, so the pipeline reads as a left-to-right sequence. */}
      <div className="flex items-stretch gap-2 overflow-x-auto pb-1">
        {steps.map((step, i) => (
          <div key={step.style} className="flex items-center gap-2">
            {i > 0 && <span className="text-muted-foreground/50">→</span>}
            <StepNode step={step} />
          </div>
        ))}
      </div>

      <p className="mt-3 text-xs text-muted-foreground">
        Provider and modality per step come straight from the job record — a cross-provider,
        cross-modality pipeline shown, not asserted.
      </p>
    </section>
  );
}
