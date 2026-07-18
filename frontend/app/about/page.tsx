import type { Metadata } from "next";
import Link from "next/link";
import { Camera, Gauge, ImageIcon, ShieldCheck, Terminal, Wand2 } from "lucide-react";

import { CtaBand } from "@/components/marketing/cta-band";
import { MarketingHeader } from "@/components/marketing/marketing-header";
import { MarketingPageHero } from "@/components/marketing/page-hero";
import { Section } from "@/components/marketing/section";
import { TrustStrip } from "@/components/marketing/trust-strip";
import { FadeIn } from "@/components/motion/fade-in";
import { Stagger, StaggerItem } from "@/components/motion/stagger";
import { SiteFooter } from "@/components/site-footer";
import { buttonVariants } from "@/components/ui/button";

export const metadata: Metadata = {
  title: "About · OriginShot",
  description:
    "Why OriginShot exists: studio-grade product catalogs from one phone photo, with cryptographic proof of what's real and what's AI.",
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
    body: "Provenance isn't a footnote. Every asset is verifiable from its own bytes, so a buyer never has to take our word for it.",
  },
  {
    icon: Gauge,
    title: "Production-minded",
    body: "Enforced auth with no dev bypass, per-account isolation, credit holds settled against real provider cost, and durable storage — the boring parts that make it real.",
  },
  {
    icon: Terminal,
    title: "Machine-true in mono",
    body: "Every hash, SKU, model name, and dimension is set in mono. Sans is what we claim; mono is what you can check.",
  },
];

export default function AboutPage() {
  return (
    <div className="min-h-dvh">
      <MarketingHeader />
      <main>
        <MarketingPageHero
          eyebrow="About OriginShot"
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

        <Section>
          <div className="grid items-stretch gap-4 lg:grid-cols-2">
            <FadeIn className="h-full">
              <div className="flex h-full flex-col rounded-lg border bg-card p-7">
                <span className="mb-5 inline-grid size-10 place-items-center rounded-md border bg-muted text-muted-foreground">
                  <Camera className="size-4" />
                </span>
                <h2 className="text-xl font-semibold tracking-tight">The problem</h2>
                <p className="mt-3 text-pretty text-muted-foreground">
                  Good product photography is the difference between a sale and a scroll — yet for
                  tens of millions of online sellers it means renting a studio, booking a model, and
                  re-shooting every colourway. It&apos;s slow, expensive, and out of reach for a solo
                  maker. Meanwhile AI imagery is filling marketplaces with no way for a buyer to tell
                  what&apos;s real.
                </p>
              </div>
            </FadeIn>

            <FadeIn delay={0.08} className="h-full">
              <div className="flex h-full flex-col rounded-lg border bg-card p-7">
                <span className="mb-5 inline-grid size-10 place-items-center rounded-md border bg-muted text-muted-foreground">
                  <Wand2 className="size-4" />
                </span>
                <h2 className="text-xl font-semibold tracking-tight">What OriginShot does</h2>
                <p className="mt-3 text-pretty text-muted-foreground">
                  Upload one snapshot and OriginShot returns a full pack — a studio shot, lifestyle
                  scenes, an on-model image, colour and angle variants, and a short product video.
                  Every output is stored durably on Backblaze B2 and carries an embedded provenance
                  manifest, so authenticity travels with the file and doubles as AI disclosure.
                </p>
              </div>
            </FadeIn>
          </div>
        </Section>

        <div className="border-y bg-card">
          <Section
            eyebrow="Principles"
            title="What we optimise for"
            description="A gallery-grade studio crossed with a precise instrument — quiet craft, and trust you can check rather than trust you're asked for."
          >
            <Stagger className="mt-10 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
              {PRINCIPLES.map(({ icon: Icon, title, body }) => (
                <StaggerItem key={title} className="h-full">
                  <div className="flex h-full flex-col rounded-lg border bg-background p-6">
                    <span className="mb-4 inline-grid size-9 place-items-center rounded-md border bg-muted text-muted-foreground">
                      <Icon className="size-4" />
                    </span>
                    <h3 className="font-semibold tracking-tight">{title}</h3>
                    <p className="mt-2 text-sm text-muted-foreground">{body}</p>
                  </div>
                </StaggerItem>
              ))}
            </Stagger>
          </Section>
        </div>

        <Section
          eyebrow="The stack"
          title="Generate with Genblaze. Store on Backblaze B2."
          description="OriginShot was built for the Backblaze Generative Media Hackathon — to show how AI media moves from prompt, to pipeline, to durable storage, without losing track of where any of it came from."
        >
          <div className="mt-10">
            <TrustStrip />
          </div>
        </Section>

        <CtaBand />
      </main>
      <SiteFooter />
    </div>
  );
}
