"use client";

import { AlertTriangle, CheckCircle2, CircleDashed } from "lucide-react";

import { cn } from "@/lib/utils";
import type { AdminHealth } from "@/lib/types";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

function uptime(seconds: number): string {
  if (seconds < 60) return `${seconds}s`;
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m`;
  if (seconds < 86_400) return `${Math.floor(seconds / 3600)}h ${Math.floor((seconds % 3600) / 60)}m`;
  return `${Math.floor(seconds / 86_400)}d ${Math.floor((seconds % 86_400) / 3600)}h`;
}

function Row({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="flex items-baseline justify-between gap-3 py-1.5">
      <span className="text-sm text-muted-foreground">{label}</span>
      <span className="tabular truncate font-mono text-sm">{value}</span>
    </div>
  );
}

/**
 * Live dependency health. Every check here round-trips to the real dependency (the deep
 * variant of /healthz), which is why it reports latency — a check that only read an env var
 * would have nothing meaningful to time.
 */
export function HealthPanel({ health }: { health: AdminHealth }) {
  return (
    <Card>
      <CardHeader className="flex-row items-center justify-between gap-3 space-y-0">
        <CardTitle>Service health</CardTitle>
        <span
          className={cn(
            "inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-medium",
            health.status === "ok"
              ? "bg-verified/12 text-verified"
              : "bg-warning/12 text-warning",
          )}
        >
          {health.status === "ok" ? (
            <CheckCircle2 className="size-3.5" />
          ) : (
            <AlertTriangle className="size-3.5" />
          )}
          {health.status}
        </span>
      </CardHeader>
      <CardContent className="space-y-4">
        <ul className="divide-y">
          {health.checks.map((check) => (
            <li key={check.name} className="flex items-center gap-3 py-2">
              {check.ok ? (
                <CheckCircle2 className="size-4 shrink-0 text-verified" />
              ) : (
                <AlertTriangle className="size-4 shrink-0 text-danger" />
              )}
              <span className="flex-1 text-sm font-medium capitalize">{check.name}</span>
              {check.detail && (
                <span className="truncate font-mono text-xs text-muted-foreground">
                  {check.detail}
                </span>
              )}
              <span className="tabular shrink-0 font-mono text-xs text-muted-foreground">
                {check.latency_ms != null ? `${check.latency_ms}ms` : "—"}
              </span>
            </li>
          ))}
        </ul>

        <div className="border-t pt-2">
          <Row label="Environment" value={health.env} />
          <Row label="Generation mode" value={health.generation_mode} />
          <Row label="Job queue" value={health.job_queue} />
          <Row label="Manifest embedding" value={health.manifest_embed_mode} />
          <Row label="Uptime" value={uptime(health.uptime_seconds)} />
        </div>

        <div className="border-t pt-3">
          <p className="mb-2 text-xs font-medium uppercase tracking-wide text-muted-foreground">
            Providers
          </p>
          <div className="flex flex-wrap gap-1.5">
            {Object.entries(health.providers).map(([name, configured]) => (
              <span
                key={name}
                className={cn(
                  "inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-xs",
                  configured
                    ? "border-transparent bg-secondary text-secondary-foreground"
                    : "text-muted-foreground",
                )}
              >
                {configured ? (
                  <CheckCircle2 className="size-3" />
                ) : (
                  <CircleDashed className="size-3" />
                )}
                {name}
              </span>
            ))}
          </div>
          {/* Stated outright: a configured key says nothing about the account's balance. */}
          <p className="mt-2 text-xs text-muted-foreground">
            Configured ≠ funded — a provider with a valid key can still fail at submit time
            if its account is out of credit.
          </p>
        </div>
      </CardContent>
    </Card>
  );
}
