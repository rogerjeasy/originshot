import { Database, Gauge, ShieldCheck, Workflow } from "lucide-react";
import type { LucideIcon } from "lucide-react";

import { Stagger, StaggerItem } from "@/components/motion/stagger";
import { MarketingSection } from "./section";

interface Value {
  icon: LucideIcon;
  title: string;
  body: string;
  tag: string;
}

const VALUES: Value[] = [
  {
    icon: ShieldCheck,
    title: "Made for real sellers",
    body: "Studio-grade catalogs are the daily, paid-for pain of millions of Etsy, Shopify, Amazon and eBay sellers. OriginShot removes the shoot entirely.",
    tag: "real-world utility",
  },
  {
    icon: Gauge,
    title: "Production-ready",
    body: "Firebase Auth with per-user isolation, multi-provider fallback, async jobs, rate limits and denial-of-wallet quotas — not a demo.",
    tag: "reliable",
  },
  {
    icon: Database,
    title: "Durable on Backblaze B2",
    body: "Every asset, thumbnail, manifest and analytics record lives on B2 — content-addressable, so identical bytes are stored exactly once.",
    tag: "b2 storage",
  },
  {
    icon: Workflow,
    title: "Orchestrated by Genblaze",
    body: "Multi-step, chained pipelines — image → variants → video — with provider fallback chains and embedded, verifiable provenance manifests.",
    tag: "genblaze",
  },
];

export function WhyOriginShot() {
  return (
    <MarketingSection
      eyebrow="Why OriginShot"
      title="Built useful, creative, and production-minded"
      description="From prompt to pipeline to durable storage — the way generative media is supposed to ship."
      className="border-b"
    >
      <Stagger className="grid gap-4 sm:grid-cols-2">
        {VALUES.map(({ icon: Icon, title, body, tag }) => (
          <StaggerItem key={title} className="h-full">
            <div className="lift flex h-full flex-col rounded-2xl border bg-card p-6">
              <div className="mb-4 flex items-center gap-3">
                <span className="inline-grid size-10 place-items-center rounded-xl bg-secondary text-foreground ring-1 ring-border">
                  <Icon className="size-5" />
                </span>
                <span className="font-mono text-xs uppercase tracking-wider text-accent">{tag}</span>
              </div>
              <h3 className="font-semibold tracking-tight">{title}</h3>
              <p className="mt-2 text-sm text-muted-foreground">{body}</p>
            </div>
          </StaggerItem>
        ))}
      </Stagger>
    </MarketingSection>
  );
}
