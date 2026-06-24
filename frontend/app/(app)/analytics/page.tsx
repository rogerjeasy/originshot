"use client";

import { BarChart3 } from "lucide-react";

import { useApiData } from "@/lib/use-api";
import type { Analytics } from "@/lib/types";
import { EmptyState } from "@/components/empty-state";
import { FadeIn } from "@/components/motion/fade-in";
import { Stagger, StaggerItem } from "@/components/motion/stagger";
import { PageHeader } from "@/components/page-header";
import { ProviderChart } from "@/components/provider-chart";
import { StatCard } from "@/components/stat-card";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";

export default function AnalyticsPage() {
  const { data, loading, error } = useApiData<Analytics>("/api/analytics");

  const stats = data
    ? [
        { label: "Total assets", value: data.total_assets },
        { label: "Unique objects", value: data.unique_objects },
        {
          label: "Dedup savings",
          value: data.dedup_savings_pct,
          decimals: 1,
          suffix: "%",
          accent: true,
        },
        { label: "Est. cost", value: data.estimated_cost_usd, decimals: 2, prefix: "$" },
        { label: "Images", value: data.images },
        { label: "Videos", value: data.videos },
        {
          label: "Fallback rate",
          value: data.fallback_rate,
          decimals: 1,
          suffix: "%",
          hint: "primary model failed, fallback succeeded",
        },
      ]
    : [];

  return (
    <div className="space-y-8">
      <PageHeader
        title="Analytics"
        description="Storage, dedup savings, generation cost, and provider reliability."
      />

      {loading ? (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <Skeleton key={i} className="h-28" />
          ))}
        </div>
      ) : error || !data ? (
        <EmptyState
          icon={BarChart3}
          title="No analytics yet"
          description="Generate your first pack and storage, cost, and provider stats will appear here."
        />
      ) : (
        <>
          <Stagger className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {stats.map((s) => (
              <StaggerItem key={s.label}>
                <StatCard {...s} />
              </StaggerItem>
            ))}
          </Stagger>

          <FadeIn delay={0.1}>
            <Card>
              <CardHeader>
                <CardTitle>Provider mix</CardTitle>
              </CardHeader>
              <CardContent>
                {Object.keys(data.provider_mix).length ? (
                  <ProviderChart data={data.provider_mix} />
                ) : (
                  <p className="text-sm text-muted-foreground">No generations yet.</p>
                )}
              </CardContent>
            </Card>
          </FadeIn>
        </>
      )}
    </div>
  );
}
