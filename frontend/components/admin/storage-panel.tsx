"use client";

import { Database, HardDrive } from "lucide-react";

import type { AdminOverview, B2Stats } from "@/lib/types";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  const units = ["KB", "MB", "GB", "TB"];
  let value = bytes / 1024;
  let unit = 0;
  while (value >= 1024 && unit < units.length - 1) {
    value /= 1024;
    unit += 1;
  }
  return `${value.toFixed(value >= 100 ? 0 : 1)} ${units[unit]}`;
}

const PREFIX_LABELS: Record<string, string> = {
  assets: "Generated & original media",
  manifests: "Provenance manifests",
  exports: "Marketplace export packs",
};

/**
 * Backblaze B2 bucket state, counted live from the object store rather than inferred from
 * our own database. That distinction is the point: it's the difference between "we think we
 * wrote 412 objects" and "the bucket contains 412 objects".
 */
export function StoragePanel({
  b2,
  overview,
}: {
  b2: B2Stats;
  overview: AdminOverview;
}) {
  const dedupSaved = overview.dedup_savings_pct;

  return (
    <Card>
      <CardHeader className="flex-row items-center justify-between gap-3 space-y-0">
        <CardTitle>Object storage</CardTitle>
        <span className="inline-flex items-center gap-1.5 font-mono text-xs text-muted-foreground">
          {b2.backend === "b2" ? (
            <Database className="size-3.5" />
          ) : (
            <HardDrive className="size-3.5" />
          )}
          {b2.backend === "b2" ? `${b2.bucket} · ${b2.region}` : "local (dev)"}
        </span>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="grid grid-cols-2 gap-4">
          <div>
            <p className="text-xs uppercase tracking-wide text-muted-foreground">Objects</p>
            <p className="tabular text-2xl font-semibold tracking-tight">
              {b2.objects.toLocaleString()}
            </p>
          </div>
          <div>
            <p className="text-xs uppercase tracking-wide text-muted-foreground">Stored</p>
            <p className="tabular text-2xl font-semibold tracking-tight">
              {formatBytes(b2.bytes)}
            </p>
          </div>
        </div>

        {b2.by_prefix && Object.keys(b2.by_prefix).length > 0 && (
          <ul className="divide-y border-t pt-1">
            {Object.entries(b2.by_prefix)
              .sort(([, a], [, b]) => b - a)
              .map(([prefix, count]) => (
                <li key={prefix} className="flex items-baseline justify-between gap-3 py-2">
                  <span className="min-w-0 truncate text-sm">
                    <span className="font-mono text-xs text-muted-foreground">{prefix}/</span>
                    <span className="ms-2 text-muted-foreground">
                      {PREFIX_LABELS[prefix] ?? ""}
                    </span>
                  </span>
                  <span className="tabular shrink-0 font-mono text-sm">
                    {count.toLocaleString()}
                  </span>
                </li>
              ))}
          </ul>
        )}

        <div className="border-t pt-3">
          <div className="flex items-baseline justify-between gap-3">
            <span className="text-sm text-muted-foreground">
              Content-addressed dedup savings
            </span>
            <span className="tabular font-mono text-sm font-semibold text-verified">
              {dedupSaved.toFixed(1)}%
            </span>
          </div>
          <div className="flex items-baseline justify-between gap-3 pt-1.5">
            <span className="text-sm text-muted-foreground">Assets with embedded C2PA</span>
            <span className="tabular font-mono text-sm font-semibold">
              {overview.embedded_pct.toFixed(1)}%
            </span>
          </div>
        </div>

        {b2.truncated && (
          <p className="text-xs text-warning">
            Listing truncated at the scan limit — object and byte totals are a lower bound.
          </p>
        )}
        {b2.error && (
          <p className="text-xs text-danger">Storage unreachable ({b2.error}).</p>
        )}
      </CardContent>
    </Card>
  );
}
