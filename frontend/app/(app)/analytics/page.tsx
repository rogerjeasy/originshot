"use client";

import { BarChart3 } from "lucide-react";

import { useApiData } from "@/lib/use-api";
import type { Analytics } from "@/lib/types";
import { EmptyState } from "@/components/empty-state";
import { FadeIn } from "@/components/motion/fade-in";
import { ProviderChart } from "@/components/provider-chart";
import { StatCard, StatGrid } from "@/components/stat-card";
import { PageToolbar } from "@/components/workbench/page-toolbar";
import { Section, Stack } from "@/components/workbench/section";
import { Alert } from "@/components/ui/alert";
import { Skeleton } from "@/components/ui/skeleton";

export default function AnalyticsPage() {
  const { data, loading, error } = useApiData<Analytics>("/api/analytics");

  // Headline figures first, then the ones you go looking for.
  const headline = data
    ? [
        { label: "Total assets", value: data.total_assets },
        {
          label: "Unique objects",
          value: data.unique_objects,
          hint: "distinct content hashes",
        },
        {
          label: "Storage saved",
          value: data.dedup_savings_pct,
          decimals: 1,
          suffix: "%",
          tone: "verified" as const,
          hint: "duplicate bytes never written",
        },
        {
          label: "Generation spend",
          value: data.actual_cost_usd,
          decimals: 2,
          prefix: "$",
          hint: "provider-billed, ledger-settled",
        },
      ]
    : [];

  const secondary = data
    ? [
        { label: "Images", value: data.images },
        { label: "Videos", value: data.videos },
        {
          label: "Fallback rate",
          value: data.fallback_rate,
          decimals: 1,
          suffix: "%",
          tone: data.fallback_rate > 10 ? ("warning" as const) : ("default" as const),
          hint: "primary model failed, fallback succeeded",
        },
        {
          label: "Est. at list prices",
          value: data.estimated_cost_usd,
          decimals: 2,
          prefix: "$",
          hint: "what this catalog would quote today",
        },
      ]
    : [];

  return (
    <Stack>
      <PageToolbar
        title="Analytics"
        description="What you've generated, what it cost, and how much storage deduplication saved."
      />

      {loading ? (
        <div className="space-y-10">
          <div className="grid gap-px overflow-hidden rounded-lg border bg-border sm:grid-cols-2 lg:grid-cols-4">
            {Array.from({ length: 4 }).map((_, i) => (
              <div key={i} className="bg-card p-5">
                <Skeleton className="h-3 w-24" />
                <Skeleton className="mt-3 h-7 w-16" />
              </div>
            ))}
          </div>
          <Skeleton className="h-56 rounded-lg" />
        </div>
      ) : error ? (
        <Alert title="Couldn't load analytics">{error}</Alert>
      ) : !data || data.total_assets === 0 ? (
        <EmptyState
          icon={BarChart3}
          title="Nothing to measure yet"
          description="Generate your first pack and storage, cost, and provider figures will appear here."
        />
      ) : (
        <>
          {/* The two rows were previously unlabelled and identical in weight, so
              the split between them carried no information. Naming each says why
              there are two. */}
          <FadeIn>
            <Section label="Output and cost">
              <StatGrid>
                {headline.map((s) => (
                  <StatCard key={s.label} {...s} />
                ))}
              </StatGrid>
            </Section>
          </FadeIn>

          <FadeIn delay={0.06}>
            <Section label="Breakdown">
              <StatGrid>
                {secondary.map((s) => (
                  <StatCard key={s.label} {...s} />
                ))}
              </StatGrid>
            </Section>
          </FadeIn>

          <FadeIn delay={0.12}>
            <Section
              label="Provider mix"
              description="Which model actually produced each asset, including fallbacks."
            >
              <ProviderChart data={data.provider_mix} />
            </Section>
          </FadeIn>
        </>
      )}
    </Stack>
  );
}
