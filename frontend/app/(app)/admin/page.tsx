"use client";

import { useCallback, useEffect, useState } from "react";
import { RefreshCw, ShieldAlert } from "lucide-react";

import { apiFetch } from "@/lib/api";
import { useSession } from "@/lib/use-session";
import type {
  AdminHealth,
  AdminJobRow,
  AdminOverview,
  AdminUserRow,
  LedgerEntry,
} from "@/lib/types";
import { HealthPanel } from "@/components/admin/health-panel";
import { JobsFeed } from "@/components/admin/jobs-feed";
import { LedgerFeed } from "@/components/admin/ledger-feed";
import { ProviderBudgetPanel } from "@/components/admin/provider-budget-panel";
import { StoragePanel } from "@/components/admin/storage-panel";
import { EmptyState } from "@/components/empty-state";
import { FadeIn } from "@/components/motion/fade-in";
import { Stagger, StaggerItem } from "@/components/motion/stagger";
import { PageHeader } from "@/components/page-header";
import { ProviderChart } from "@/components/provider-chart";
import { StatCard } from "@/components/stat-card";
import { UsersTable } from "@/components/admin/users-table";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";

interface AdminData {
  overview: AdminOverview;
  health: AdminHealth;
  users: AdminUserRow[];
  jobs: AdminJobRow[];
  ledger: LedgerEntry[];
}

function formatMs(ms: number | null | undefined): string {
  if (ms == null) return "—";
  return ms < 1000 ? `${ms}ms` : `${(ms / 1000).toFixed(1)}s`;
}

export default function AdminPage() {
  const { isAdmin, loading: sessionLoading } = useSession();
  const [data, setData] = useState<AdminData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setError(null);
    try {
      // One round of parallel reads rather than five sequential ones — the panels are
      // independent and the dashboard should settle in a single paint.
      const [overview, health, users, jobs, ledger] = await Promise.all([
        apiFetch<AdminOverview>("/api/admin/overview"),
        apiFetch<AdminHealth>("/api/admin/health"),
        apiFetch<AdminUserRow[]>("/api/admin/users"),
        apiFetch<AdminJobRow[]>("/api/admin/jobs?limit=25"),
        apiFetch<LedgerEntry[]>("/api/admin/ledger?limit=25"),
      ]);
      setData({ overview, health, users, jobs, ledger });
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load admin data");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (sessionLoading) return;
    if (!isAdmin) {
      setLoading(false);
      return;
    }
    void load();
  }, [isAdmin, sessionLoading, load]);

  if (sessionLoading || (loading && isAdmin)) {
    return (
      <div className="space-y-8">
        <PageHeader title="Admin" description="Platform operations, spend, and health." />
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {Array.from({ length: 8 }).map((_, i) => (
            <Skeleton key={i} className="h-28" />
          ))}
        </div>
      </div>
    );
  }

  // The server enforces this on every /api/admin route; this is the matching client state
  // for a non-admin who navigated here directly.
  if (!isAdmin) {
    return (
      <div className="space-y-8">
        <PageHeader title="Admin" description="Platform operations, spend, and health." />
        <EmptyState
          icon={ShieldAlert}
          title="Admin access required"
          description="This dashboard is limited to accounts holding the admin role."
        />
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="space-y-8">
        <PageHeader title="Admin" description="Platform operations, spend, and health." />
        <EmptyState
          icon={ShieldAlert}
          title="Couldn't load the dashboard"
          description={error ?? "No data returned."}
        />
        <div className="flex justify-center">
          <Button variant="outline" onClick={() => void load()}>
            <RefreshCw /> Retry
          </Button>
        </div>
      </div>
    );
  }

  const { overview, health, users, jobs, ledger } = data;

  const stats = [
    { label: "Users", value: overview.users_total, hint: `${overview.users_active_7d} active this week` },
    { label: "Products", value: overview.skus_total },
    { label: "Assets", value: overview.assets_total, hint: `${overview.generated_24h} generated in 24h` },
    {
      label: "Job success",
      value: overview.success_rate_pct,
      decimals: 1,
      suffix: "%",
      accent: overview.success_rate_pct >= 95,
      hint: `${overview.jobs_succeeded} ok · ${overview.jobs_partial} partial · ${overview.jobs_failed} failed`,
    },
    {
      label: "Platform spend",
      value: overview.spend_total_usd,
      decimals: 2,
      prefix: "$",
      hint: "actual provider cost",
    },
    {
      label: "Credits outstanding",
      value: overview.credits_outstanding_usd,
      decimals: 2,
      prefix: "$",
      hint: `$${overview.credits_granted_usd.toFixed(2)} granted lifetime`,
    },
    { label: "Images", value: overview.images },
    { label: "Videos", value: overview.videos },
  ];

  return (
    <div className="space-y-8">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <PageHeader title="Admin" description="Platform operations, spend, and health." />
        <Button variant="outline" size="sm" onClick={() => void load()}>
          <RefreshCw /> Refresh
        </Button>
      </div>

      <Stagger className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {stats.map((s) => (
          <StaggerItem key={s.label}>
            <StatCard {...s} />
          </StaggerItem>
        ))}
      </Stagger>

      <div className="grid gap-6 lg:grid-cols-2">
        <FadeIn>
          <HealthPanel health={health} />
        </FadeIn>
        <FadeIn delay={0.05}>
          <StoragePanel b2={overview.b2} overview={overview} />
        </FadeIn>
        {overview.provider_budget && (
          <FadeIn delay={0.08}>
            <ProviderBudgetPanel
              budget={overview.provider_budget}
              onChanged={() => void load()}
            />
          </FadeIn>
        )}
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <FadeIn delay={0.1}>
          <Card>
            <CardHeader>
              <CardTitle>Generation latency</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <p className="text-xs uppercase tracking-wide text-muted-foreground">
                    Median (p50)
                  </p>
                  <p className="tabular text-3xl font-semibold tracking-tight">
                    {formatMs(overview.p50_duration_ms)}
                  </p>
                </div>
                <div>
                  <p className="text-xs uppercase tracking-wide text-muted-foreground">
                    Slowest 5% (p95)
                  </p>
                  <p className="tabular text-3xl font-semibold tracking-tight">
                    {formatMs(overview.p95_duration_ms)}
                  </p>
                </div>
              </div>
              <p className="mt-3 text-sm text-muted-foreground">
                Measured from when the worker picked the job up to when the last style
                finished — queue wait is excluded.
              </p>
            </CardContent>
          </Card>
        </FadeIn>

        <FadeIn delay={0.15}>
          <Card>
            <CardHeader>
              <CardTitle>Provider mix</CardTitle>
            </CardHeader>
            <CardContent>
              {Object.keys(overview.provider_mix).length ? (
                <ProviderChart data={overview.provider_mix} />
              ) : (
                <p className="text-sm text-muted-foreground">No generations yet.</p>
              )}
            </CardContent>
          </Card>
        </FadeIn>
      </div>

      <FadeIn delay={0.2}>
        <UsersTable users={users} onChanged={() => void load()} />
      </FadeIn>

      <div className="grid gap-6 lg:grid-cols-2">
        <FadeIn delay={0.25}>
          <JobsFeed jobs={jobs} />
        </FadeIn>
        <FadeIn delay={0.3}>
          <LedgerFeed entries={ledger} />
        </FadeIn>
      </div>
    </div>
  );
}
