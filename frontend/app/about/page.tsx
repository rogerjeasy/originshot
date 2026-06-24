import type { Metadata } from "next";
import Link from "next/link";
import { Camera, Gauge, ImageIcon, ShieldCheck, Sparkles, Wand2 } from "lucide-react";

import { CtaBand } from "@/components/marketing/cta-band";
import { MarketingHeader } from "@/components/marketing/marketing-header";
import { MarketingPageHero } from "@/components/marketing/page-hero";
import { MarketingSection } from "@/components/marketing/section";
import { TrustStrip } from "@/components/marketing/trust-strip";
import { FadeIn } from "@/components/motion/fade-in";
import { Stagger, StaggerItem } from "@/components/motion/stagger";
import { SiteFooter } from "@/components/site-footer";
import { buttonVariants } from "@/components/ui/button";

export const metadata: Metadata = {
  title: "About · ListSnap",
  description:
    "Why ListSnap exists: studio-grade product catalogs from one phone photo, with cryptographic proof of what's real and what's AI.",
};

const PRINCIPLES = [
  {
    icon: ImageIcon,
    title: "Image-first",
    body: "The generated media is the hero of every screen — framed like gallery objects, never buried under chrome.",
  },
  {
    icon: ShieldCheck,
    title: "Trust by design",
    body: "Provenance isn't a footnote. Every asset is verifiable from its own bytes, so buyers never have to take our word for it.",
  },
  {
    icon: Gauge,
    title: "Production-minded",
    body: "Auth, per-user isolation, multi-provider fallback, quotas and durable storage — the boring parts that make it real.",
  },
  {
    icon: Sparkles,
    title: "Provenance-native",
    body: "Geist Mono carries every hash, SKU and model name. Machine-true detail is part of the brand, not an afterthought.",
  },
];

export default function AboutPage() {
  return (
    <div className="min-h-dvh">
      <MarketingHeader />
      <main>
        <MarketingPageHero
          eyebrow="About ListSnap"
          title="Studio-grade catalogs, honest about what's real"
          description="One phone photo in, a full marketplace-ready catalog out — with cryptographic proof of what's authentic and what's AI."
        >
          <Link href="/studio" className={buttonVariants({ variant: "accent", size: "lg" })}>
            <Wand2 /> Start free
          </Link>
          <Link href="/how-it-works" className={buttonVariants({ variant: "outline", size: "lg" })}>
            How it works
          </Link>
        </MarketingPageHero>

        <MarketingSection className="border-b">
          <div className="grid items-stretch gap-6 lg:grid-cols-2">
            <FadeIn className="h-full">
              <div className="flex h-full flex-col rounded-2xl border bg-card p-7">
                <span className="mb-4 inline-grid size-10 place-items-center rounded-xl bg-secondary ring-1 ring-border">
                  <Camera className="size-5" />
                </span>
                <h2 className="text-xl font-semibold tracking-tight">The problem</h2>
                <p className="mt-3 text-pretty text-muted-foreground">
                  Great product photography is the difference between a sale and a scroll — yet for
                  tens of millions of online sellers it means renting studios, booking models, and
                  re-shooting every colorway. It&apos;s slow, expensive, and out of reach for solo
                  makers. Meanwhile AI imagery is flooding marketplaces with no way for buyers to
                  tell what&apos;s real.
                </p>
              </div>
            </FadeIn>

            <FadeIn delay={0.08} className="h-full">
              <div className="studio-sweep flex h-full flex-col rounded-2xl border p-7">
                <span className="mb-4 inline-grid size-10 place-items-center rounded-xl bg-accent/10 text-accent ring-1 ring-accent/20">
                  <Wand2 className="size-5" />
                </span>
                <h2 className="text-xl font-semibold tracking-tight">What ListSnap does</h2>
                <p className="mt-3 text-pretty text-muted-foreground">
                  Upload one snapshot and ListSnap generates a full pack — studio shots, lifestyle
                  scenes, on-model images, color and angle variants, and a short product video.
                  Every output is stored durably on Backblaze B2 and carries an embedded provenance
                  manifest, so authenticity travels with the file and doubles as AI-disclosure
                  compliance.
                </p>
              </div>
            </FadeIn>
          </div>
        </MarketingSection>

        <MarketingSection
          eyebrow="Principles"
          title="What we optimize for"
          description="A gallery-grade studio crossed with a precise developer tool — quiet craft, real trust."
          className="border-b"
        >
          <Stagger className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {PRINCIPLES.map(({ icon: Icon, title, body }) => (
              <StaggerItem key={title} className="h-full">
                <div className="lift flex h-full flex-col rounded-2xl border bg-card p-6">
                  <span className="mb-4 inline-grid size-10 place-items-center rounded-xl bg-secondary ring-1 ring-border">
                    <Icon className="size-5" />
                  </span>
                  <h3 className="font-semibold tracking-tight">{title}</h3>
                  <p className="mt-2 text-sm text-muted-foreground">{body}</p>
                </div>
              </StaggerItem>
            ))}
          </Stagger>
        </MarketingSection>

        <MarketingSection
          eyebrow="The stack"
          title="Generate with Genblaze. Store on Backblaze B2."
          description="ListSnap was built for the Backblaze Generative Media Hackathon — to show how AI media moves from prompt to pipeline to durable storage."
          className="border-b"
        >
          <TrustStrip />
        </MarketingSection>

        <CtaBand />
      </main>
      <SiteFooter />
    </div>
  );
}
