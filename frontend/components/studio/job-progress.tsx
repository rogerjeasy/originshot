"use client";

import { useEffect, useRef, useState } from "react";
import {
  AlertTriangle,
  Check,
  Clock,
  Loader2,
  MinusCircle,
  Sparkles,
} from "lucide-react";

import { cn } from "@/lib/utils";
import type { Job, JobStep, StepStatus } from "@/lib/types";
import { Card, CardContent } from "@/components/ui/card";

const STYLE_LABELS: Record<string, string> = {
  studio: "Studio white-background",
  lifestyle: "Lifestyle scenes",
  onmodel: "On-model",
  variant: "Colour & angle variants",
  video: "Hero video",
  original: "Original",
};

/** mm:ss — the only format that stays readable at a glance while a number is ticking. */
function formatClock(totalSeconds: number): string {
  const s = Math.max(0, Math.floor(totalSeconds));
  return `${String(Math.floor(s / 60)).padStart(1, "0")}:${String(s % 60).padStart(2, "0")}`;
}

function formatDuration(ms: number): string {
  return ms < 1000 ? `${ms}ms` : `${(ms / 1000).toFixed(1)}s`;
}

/**
 * Ticking elapsed time since `startedAt`.
 *
 * Derived from a server timestamp rather than counted up from a local zero, so the number
 * survives a remount (navigating away and back mid-job) and doesn't drift from the duration
 * the server will eventually record. Stops as soon as the job is no longer running.
 */
function useElapsed(startedAt: string | null | undefined, running: boolean): number {
  const [now, setNow] = useState(() => Date.now());

  useEffect(() => {
    if (!running) return;
    const id = setInterval(() => setNow(Date.now()), 250);
    return () => clearInterval(id);
  }, [running]);

  if (!startedAt) return 0;
  const start = new Date(startedAt).getTime();
  if (Number.isNaN(start)) return 0;
  return Math.max(0, (now - start) / 1000);
}

const STEP_ICON: Record<StepStatus, React.ComponentType<{ className?: string }>> = {
  pending: Clock,
  running: Loader2,
  done: Check,
  failed: AlertTriangle,
  skipped: MinusCircle,
};

function StepRow({ step }: { step: JobStep }) {
  const Icon = STEP_ICON[step.status];
  const running = step.status === "running";
  const elapsed = useElapsed(step.started_at, running);

  return (
    <li className="flex items-center gap-3 py-2.5">
      <span
        className={cn(
          "grid size-6 shrink-0 place-items-center rounded-full border",
          step.status === "done" && "border-transparent bg-verified/12 text-verified",
          running && "border-transparent bg-accent/12 text-accent",
          step.status === "failed" && "border-transparent bg-danger/12 text-danger",
          step.status === "skipped" && "border-transparent bg-muted text-muted-foreground",
          step.status === "pending" && "text-muted-foreground",
        )}
      >
        <Icon className={cn("size-3.5", running && "animate-spin")} />
      </span>

      <div className="min-w-0 flex-1">
        <p
          className={cn(
            "truncate text-sm",
            step.status === "pending" ? "text-muted-foreground" : "font-medium",
          )}
        >
          {STYLE_LABELS[step.style] ?? step.style}
        </p>
        {/* Only ever show what the server actually reported — never invent a provider name. */}
        {step.status === "done" && step.provider && (
          <p className="truncate font-mono text-xs text-muted-foreground">
            {step.provider}
            {step.model ? ` · ${step.model}` : ""}
            {step.asset_count > 1 ? ` · ${step.asset_count} images` : ""}
          </p>
        )}
        {step.status === "failed" && step.error && (
          <p className="truncate text-xs text-danger" title={step.error}>
            {step.error}
          </p>
        )}
        {step.status === "skipped" && step.error && (
          <p className="truncate text-xs text-muted-foreground" title={step.error}>
            Skipped — {step.error}
          </p>
        )}
      </div>

      <span className="tabular shrink-0 font-mono text-xs text-muted-foreground">
        {running
          ? formatClock(elapsed)
          : step.duration_ms != null
            ? formatDuration(step.duration_ms)
            : step.status === "pending" && step.eta_seconds
              ? `~${step.eta_seconds}s`
              : ""}
      </span>
    </li>
  );
}

/**
 * Live generation progress: total elapsed timer plus a real per-step breakdown.
 *
 * Every value here comes from the job document the worker writes as it goes — there is no
 * simulated progress bar. The completion fraction is steps-resolved / steps-total, so it
 * only advances when a provider call actually returns.
 */
export function JobProgress({ job }: { job: Job }) {
  const running = job.status === "queued" || job.status === "running";
  const elapsed = useElapsed(job.started_at ?? job.created_at, running);
  const eta = job.eta_seconds ?? 0;

  const steps = job.steps ?? [];
  const resolved = steps.filter((s) => s.status !== "pending" && s.status !== "running").length;
  const pct = steps.length ? Math.round((resolved / steps.length) * 100) : 0;

  // An overrun is normal (the ETA is a rough median), so it's reported plainly rather than
  // as an error state — but it is reported, not hidden behind a bar pinned at 99%.
  const overrun = running && eta > 0 && elapsed > eta;

  return (
    <Card>
      <CardContent className="p-5">
        <div className="mb-4 flex items-baseline justify-between gap-3">
          <h2 className="flex items-center gap-2 text-sm font-semibold uppercase tracking-wide text-muted-foreground">
            <Sparkles
              className={cn("size-3.5 text-accent", running && "animate-pulse")}
              aria-hidden
            />
            {running ? "Generating" : "Generation complete"}
          </h2>
          <div className="text-right">
            <span
              className="tabular text-2xl font-semibold tracking-tight"
              aria-live="polite"
              aria-label={`Elapsed ${formatClock(elapsed)}`}
            >
              {formatClock(elapsed)}
            </span>
            {eta > 0 && (
              <span className="tabular ms-1.5 font-mono text-xs text-muted-foreground">
                / ~{formatClock(eta)}
              </span>
            )}
          </div>
        </div>

        <div
          className="h-1.5 w-full overflow-hidden rounded-full bg-muted"
          role="progressbar"
          aria-valuenow={pct}
          aria-valuemin={0}
          aria-valuemax={100}
          aria-label="Generation progress"
        >
          <div
            className={cn(
              "h-full rounded-full transition-[width] duration-500 ease-out",
              job.status === "failed" ? "bg-danger" : "bg-accent",
            )}
            style={{ width: `${pct}%` }}
          />
        </div>

        <p className="mt-2 text-xs text-muted-foreground">
          {resolved} of {steps.length} steps
          {overrun && " · taking longer than usual"}
          {job.cost_actual != null && !running && ` · $${job.cost_actual.toFixed(4)} spent`}
        </p>

        <ul className="mt-2 divide-y">
          {steps.map((step) => (
            <StepRow key={step.style} step={step} />
          ))}
        </ul>
      </CardContent>
    </Card>
  );
}
