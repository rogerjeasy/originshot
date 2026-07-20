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
import { PageToolbar } from "@/components/workbench/page-toolbar";
import { ProviderChart } from "@/components/provider-chart";
import { StatCard, StatGrid } from "@/components/stat-card";
import { UsersTable } from "@/components/admin/users-table";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";

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
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setError(null);
    setRefreshing(true);
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
      setRefreshing(false);
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

  // The error/loading/denied states render the head without a Refresh control;
  // the loaded state passes one in.
  const header = (action?: React.ReactNode) => (
    <PageToolbar
      title="Admin"
      description="Platform operations, spend, and health."
      action={action}
    />
  );

  if (sessionLoading || (loading && isAdmin)) {
    return (
      <div className="space-y-10">
        {header()}
        <div className="grid gap-px overflow-hidden rounded-lg border bg-border sm:grid-cols-2 lg:grid-cols-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="bg-card p-5">
              <Skeleton className="h-3 w-24" />
              <Skeleton className="mt-3 h-7 w-16" />
            </div>
          ))}
        </div>
        <Skeleton className="h-64 rounded-lg" />
      </div>
    );
  }

  // The server enforces this on every /api/admin route; this is the matching client state
  // for a non-admin who navigated here directly.
  if (!isAdmin) {
    return (
      <div className="space-y-10">
        {header()}
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
      <div className="space-y-10">
        {header()}
        <Alert
          title="Couldn't load the dashboard"
          action={
            <Button variant="outline" size="sm" onClick={() => void load()}>
              <RefreshCw /> Retry
            </Button>
          }
        >
          {error ?? "No data returned."}
        </Alert>
      </div>
    );
  }

  const { overview, health, users, jobs, ledger } = data;

  const platform = [
    {
      label: "Users",
      value: overview.users_total,
      hint: `${overview.users_active_7d} active this week`,
    },
    { label: "Products", value: overview.skus_total },
    {
      label: "Assets",
      value: overview.assets_total,
      hint: `${overview.generated_24h} generated in 24h`,
    },
    {
      label: "Job success",
      value: overview.success_rate_pct,
      decimals: 1,
      suffix: "%",
      tone: overview.success_rate_pct >= 95 ? ("verified" as const) : ("warning" as const),
      hint: `${overview.jobs_succeeded} ok · ${overview.jobs_partial} partial · ${overview.jobs_failed} failed`,
    },
  ];

  const money = [
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
    <div className="space-y-10">
      {header(
        <Button
          variant="outline"
          size="sm"
          onClick={() => void load()}
          disabled={refreshing}
          aria-label="Refresh dashboard"
        >
          <RefreshCw className={refreshing ? "animate-spin" : undefined} />
          Refresh
        </Button>,
      )}

      <FadeIn>
        <StatGrid>
          {platform.map((s) => (
            <StatCard key={s.label} {...s} />
          ))}
        </StatGrid>
      </FadeIn>

      <Tabs defaultValue="operations">
        <TabsList>
          <TabsTrigger value="operations">Operations</TabsTrigger>
          <TabsTrigger value="users">Users ({users.length})</TabsTrigger>
          <TabsTrigger value="activity">Activity</TabsTrigger>
        </TabsList>

        <TabsContent value="operations" className="mt-6 space-y-6">
          <StatGrid>
            {money.map((s) => (
              <StatCard key={s.label} {...s} />
            ))}
          </StatGrid>

          <div className="grid gap-6 lg:grid-cols-2">
            <HealthPanel health={health} />
            <StoragePanel b2={overview.b2} overview={overview} />
            {overview.provider_budget && (
              <ProviderBudgetPanel
                budget={overview.provider_budget}
                onChanged={() => void load()}
              />
            )}

            <Card>
              <CardHeader>
                <CardTitle>Generation latency</CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <p className="label text-muted-foreground">Median (p50)</p>
                    <p className="tabular mt-1 font-mono text-[28px] font-medium leading-none tracking-tight">
                      {formatMs(overview.p50_duration_ms)}
                    </p>
                  </div>
                  <div>
                    <p className="label text-muted-foreground">Slowest 5% (p95)</p>
                    <p className="tabular mt-1 font-mono text-[28px] font-medium leading-none tracking-tight">
                      {formatMs(overview.p95_duration_ms)}
                    </p>
                  </div>
                </div>
                <p className="text-sm text-muted-foreground">
                  Measured from when the worker picked the job up to when the last style
                  finished — queue wait is excluded.
                </p>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Provider mix</CardTitle>
              </CardHeader>
              <CardContent>
                <ProviderChart data={overview.provider_mix} />
              </CardContent>
            </Card>
          </div>
        </TabsContent>

        <TabsContent value="users" className="mt-6">
          <UsersTable users={users} onChanged={() => void load()} />
        </TabsContent>

        <TabsContent value="activity" className="mt-6">
          <div className="grid gap-6 lg:grid-cols-2">
            <JobsFeed jobs={jobs} />
            <LedgerFeed entries={ledger} />
          </div>
        </TabsContent>
      </Tabs>
    </div>
  );
}
