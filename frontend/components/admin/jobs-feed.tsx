"use client";

import { cn } from "@/lib/utils";
import type { AdminJobRow, JobStatus } from "@/lib/types";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

const STATUS_STYLES: Record<JobStatus, string> = {
  done: "bg-verified/12 text-verified",
  partial: "bg-warning/12 text-warning",
  failed: "bg-danger/12 text-danger",
  running: "bg-accent/12 text-accent",
  queued: "bg-secondary text-secondary-foreground",
};

function relative(iso: string): string {
  const seconds = Math.max(0, (Date.now() - new Date(iso).getTime()) / 1000);
  if (seconds < 60) return "just now";
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`;
  if (seconds < 86_400) return `${Math.floor(seconds / 3600)}h ago`;
  return `${Math.floor(seconds / 86_400)}d ago`;
}

/** Recent generation jobs across all users — the feed for spotting failures early. */
export function JobsFeed({ jobs }: { jobs: AdminJobRow[] }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Recent jobs</CardTitle>
      </CardHeader>
      <CardContent>
        <ul className="divide-y">
          {jobs.map((job) => (
            <li key={job.id} className="flex items-center gap-3 py-2.5">
              <span
                className={cn(
                  "shrink-0 rounded-full px-2 py-0.5 text-xs font-medium",
                  STATUS_STYLES[job.status],
                )}
              >
                {job.status}
              </span>

              <div className="min-w-0 flex-1">
                <p className="truncate text-sm">
                  {job.requested_styles.join(", ") || "—"}
                  <span className="text-muted-foreground">
                    {" · "}
                    {job.asset_count} asset{job.asset_count === 1 ? "" : "s"}
                  </span>
                </p>
                <p className="truncate font-mono text-xs text-muted-foreground">
                  {job.owner_email ?? job.owner_uid}
                </p>
                {job.error && (
                  <p className="truncate text-xs text-danger" title={job.error}>
                    {job.error}
                  </p>
                )}
              </div>

              <div className="shrink-0 text-right">
                <p className="tabular font-mono text-xs">
                  {job.duration_ms != null ? `${(job.duration_ms / 1000).toFixed(1)}s` : "—"}
                </p>
                <p className="text-xs text-muted-foreground">{relative(job.created_at)}</p>
              </div>
            </li>
          ))}
        </ul>

        {jobs.length === 0 && (
          <p className="py-6 text-center text-sm text-muted-foreground">No jobs yet.</p>
        )}
      </CardContent>
    </Card>
  );
}
