"use client";

import Link from "next/link";
import {
  AlertTriangle,
  ArrowUpRight,
  Check,
  Clock,
  Loader2,
  PauseCircle,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";

import { cn } from "@/lib/utils";
import type { Batch, BatchItem, BatchItemStatus } from "@/lib/types";
import { Card, CardContent } from "@/components/ui/card";

/**
 * The live board for a catalog run.
 *
 * One row per product, and one calibration patch per product across the top — the same
 * idiom the single-SKU job uses for its styles, scaled up a level. Status is icon + text +
 * colour, never colour alone, and `blocked` reads differently from `failed` on purpose:
 * a blocked product never started and costs nothing to retry.
 */

const STATUS_LABEL: Record<BatchItemStatus, string> = {
  pending: "queued",
  running: "developing",
  done: "done",
  partial: "partial",
  failed: "failed",
  blocked: "not started",
};

const STATUS_ICON: Record<BatchItemStatus, LucideIcon> = {
  pending: Clock,
  running: Loader2,
  done: Check,
  partial: AlertTriangle,
  failed: AlertTriangle,
  blocked: PauseCircle,
};

const PATCH: Record<BatchItemStatus, string> = {
  pending: "border bg-transparent",
  running: "developing bg-accent/25",
  done: "bg-verified",
  partial: "bg-warning",
  failed: "bg-danger",
  blocked: "bg-muted",
};

const CHIP: Record<BatchItemStatus, string> = {
  pending: "text-muted-foreground",
  running: "border-transparent bg-accent/12 text-accent",
  done: "border-transparent bg-verified/12 text-verified",
  partial: "border-transparent bg-warning/12 text-warning",
  failed: "border-transparent bg-danger/12 text-danger",
  blocked: "border-transparent bg-muted text-muted-foreground",
};

function formatDuration(ms?: number | null): string | null {
  if (!ms && ms !== 0) return null;
  return ms < 1000 ? `${ms}ms` : `${(ms / 1000).toFixed(1)}s`;
}

function PatchStrip({ items }: { items: BatchItem[] }) {
  const settled = items.filter((i) => i.status !== "pending" && i.status !== "running");
  const pct = items.length ? Math.round((settled.length / items.length) * 100) : 0;
  return (
    <div
      className="flex gap-1"
      role="progressbar"
      aria-valuenow={pct}
      aria-valuemin={0}
      aria-valuemax={100}
      aria-label="Catalog progress"
    >
      {items.map((item) => (
        <span
          key={item.sku_id}
          title={`${item.title ?? item.sku_id} — ${STATUS_LABEL[item.status]}`}
          className={cn(
            "h-7 min-w-1.5 flex-1 rounded-[3px] transition-colors duration-300",
            PATCH[item.status],
          )}
        >
          <span className="sr-only">
            {item.title ?? item.sku_id}: {STATUS_LABEL[item.status]}
          </span>
        </span>
      ))}
    </div>
  );
}

function ItemRow({ item }: { item: BatchItem }) {
  const Icon = STATUS_ICON[item.status];
  const running = item.status === "running";
  const duration = formatDuration(item.duration_ms);

  return (
    <li className="flex items-start gap-3 py-2.5">
      <span
        className={cn(
          "mt-0.5 grid size-6 shrink-0 place-items-center rounded-full border",
          CHIP[item.status],
        )}
      >
        <Icon className={cn("size-3.5", running && "animate-spin")} />
      </span>

      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-baseline gap-x-2 gap-y-0.5">
          <p
            className={cn(
              "truncate text-sm",
              item.status === "pending" ? "text-muted-foreground" : "font-medium",
            )}
          >
            {item.title ?? item.sku_id}
          </p>
          <span className="label-mono text-muted-foreground">
            {STATUS_LABEL[item.status]}
          </span>
        </div>

        <p className="mt-0.5 flex flex-wrap gap-x-3 font-mono text-[11px] text-muted-foreground">
          {item.asset_count > 0 && <span>{item.asset_count} assets</span>}
          {duration && <span>{duration}</span>}
          {typeof item.cost_actual === "number" && item.cost_actual > 0 && (
            <span>${item.cost_actual.toFixed(4)}</span>
          )}
        </p>

        {item.error && (
          <p
            className={cn(
              "mt-1 text-xs",
              item.status === "blocked" ? "text-muted-foreground" : "text-danger",
            )}
          >
            {item.error}
          </p>
        )}
      </div>

      <Link
        href={`/studio/${item.sku_id}`}
        className="mt-0.5 inline-flex shrink-0 items-center gap-1 text-xs text-accent underline decoration-accent/30 underline-offset-4 hover:decoration-accent"
      >
        Open <ArrowUpRight className="size-3" />
      </Link>
    </li>
  );
}

export function CatalogBoard({ batch }: { batch: Batch }) {
  const items = batch.items ?? [];
  const done = items.filter((i) => i.status === "done").length;
  const blocked = items.filter((i) => i.status === "blocked").length;
  const running = batch.status === "queued" || batch.status === "running";

  return (
    <Card>
      <CardContent className="space-y-4 p-5">
        <div className="flex flex-wrap items-baseline justify-between gap-2">
          <div>
            <p className="label text-muted-foreground">
              {running ? "Generating catalog" : "Catalog run"}
            </p>
            <p className="mt-1 text-sm">
              <span className="tabular font-medium">
                {done} of {items.length}
              </span>{" "}
              <span className="text-muted-foreground">
                products complete
                {batch.concurrency > 1 && ` · ${batch.concurrency} at a time`}
              </span>
            </p>
          </div>
          {typeof batch.cost_actual === "number" && batch.cost_actual > 0 && (
            <p className="font-mono text-xs text-muted-foreground">
              ${batch.cost_actual.toFixed(4)} spent
            </p>
          )}
        </div>

        <PatchStrip items={items} />

        {blocked > 0 && (
          <p className="rounded-md border border-warning/25 bg-warning-surface p-3 text-sm text-warning">
            {blocked} product{blocked === 1 ? " was" : "s were"} not started — they cost
            nothing and can be re-run once the blocker below is cleared.
          </p>
        )}

        <ul className="divide-y">
          {items.map((item) => (
            <ItemRow key={item.sku_id} item={item} />
          ))}
        </ul>
      </CardContent>
    </Card>
  );
}
