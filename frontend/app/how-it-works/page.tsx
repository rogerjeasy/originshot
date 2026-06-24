import type { Metadata } from "next";
import Link from "next/link";
import { Camera, Database, Plus, ShieldCheck, Wand2, Workflow } from "lucide-react";

import { CtaBand } from "@/components/marketing/cta-band";
import { MarketingHeader } from "@/components/marketing/marketing-header";
import { MarketingPageHero } from "@/components/marketing/page-hero";
import { PipelineFlow } from "@/components/marketing/pipeline-flow";
import { ProvenanceSpotlight } from "@/components/marketing/provenance-spotlight";
import { MarketingSection } from "@/components/marketing/section";
import { StepFlow, type FlowStep } from "@/components/marketing/step-flow";
import { TrustStrip } from "@/components/marketing/trust-strip";
import { FadeIn } from "@/components/motion/fade-in";
import { SiteFooter } from "@/components/site-footer";
import { buttonVariants } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export const metadata: Metadata = {
  title: "How it works · ListSnap",
  description:
    "From one phone photo to a verified, marketplace-ready pack — the ListSnap pipeline, step by step.",
};

const STEPS: FlowStep[] = [
  {
    icon: Camera,
    title: "Upload one photo",
    body: "Drop a single phone photo. We validate it, strip EXIF/GPS for privacy, hash the bytes, and anchor it as the authentic original.",
  },
  {
    icon: Wand2,
    title: "Generate the pack",
    body: "Pick styles and target marketplaces. Genblaze orchestrates multi-step pipelines across providers to render studio, lifestyle, variant, and video outputs.",
  },
  {
    icon: ShieldCheck,
    title: "Verify & publish",
    body: "Every asset is stored on Backblaze B2 with an embedded provenance manifest. Anyone can re-check authenticity straight from the file.",
  },
];

const STACK = [
  {
    icon: Workflow,
    title: "Genblaze orchestration",
    body: "A unified pipeline API chains and swaps providers without rebuilding logic. Each run emits a SHA-256 provenance manifest with provider, model, prompt, and lineage.",
  },
  {
    icon: Database,
    title: "Backblaze B2 storage",
    body: "Content-addressable object storage holds every image, video, thumbnail, manifest, and analytics record — identical bytes stored exactly once.",
  },
];

const FAQ = [
  {
    q: "Do I need a real product shoot?",
    a: "No. A single ordinary phone photo is enough. ListSnap treats it as the authentic source and generates the rest of the catalog around it.",
  },
  {
    q: "What does “provenance-verified” actually mean?",
    a: "Every generated file carries an embedded, content-bound SHA-256 manifest. Re-hash the bytes on the Verify page and we prove whether it's an authentic original, an AI generation, or has been tampered with.",
  },
  {
    q: "Which models and providers are used?",
    a: "GMI Cloud is primary (Seedream / FLUX / Gemini for images, Kling / Seedance for video), with OpenAI, Google Imagen/Veo, and Luma as fallback — chosen per style for reliability.",
  },
  {
    q: "Where are my assets stored?",
    a: "On Backblaze B2 — durable, S3-compatible object storage. Storage is content-addressable, so duplicate outputs are deduplicated automatically.",
  },
];

export default function HowItWorksPage() {
  return (
    <div className="min-h-dvh">
      <MarketingHeader />
      <main>
        <MarketingPageHero
          eyebrow="How it works"
          title="From a single snapshot to a verified pack"
          description="No studio, no shoot, no guesswork about what's real. Here's exactly what happens between your one photo and a marketplace-ready catalog."
        >
          <Link href="/studio" className={buttonVariants({ variant: "accent", size: "lg" })}>
            <Wand2 /> Try it free
          </Link>
          <Link href="/verify" className={buttonVariants({ variant: "outline", size: "lg" })}>
            <ShieldCheck /> Verify a file
          </Link>
        </MarketingPageHero>

        <MarketingSection
          eyebrow="The flow"
          title="Three steps, start to finish"
          className="border-b"
        >
          <StepFlow steps={STEPS} />
        </MarketingSection>

        <MarketingSection
          eyebrow="Inside the pipeline"
          title="One input fans out into a full catalog"
          description="Genblaze runs a chained, multi-step pipeline — each stage feeding the next, with provider fallback if a model is slow or fails."
          className="border-b"
        >
          <FadeIn>
            <PipelineFlow />
          </FadeIn>
          <p className="mx-auto mt-6 max-w-2xl text-center text-sm text-muted-foreground">
            Model names shown are representative; ListSnap picks the best available provider per
            style at run time and records the exact one in each manifest.
          </p>
        </MarketingSection>

        <ProvenanceSpotlight />

        <MarketingSection
          eyebrow="The stack"
          title="Built on production infrastructure"
          description="Generate with Genblaze. Store on Backblaze B2. The exact pairing this is designed around."
          className="border-b"
        >
          <div className="grid gap-4 sm:grid-cols-2">
            {STACK.map(({ icon: Icon, title, body }) => (
              <Card key={title} className="lift h-full">
                <CardHeader>
                  <span className="mb-1 inline-grid size-10 place-items-center rounded-xl bg-secondary ring-1 ring-border">
                    <Icon className="size-5" />
                  </span>
                  <CardTitle className="text-base">{title}</CardTitle>
                </CardHeader>
                <CardContent>
                  <p className="text-sm text-muted-foreground">{body}</p>
                </CardContent>
              </Card>
            ))}
          </div>
          <TrustStrip className="mt-10" />
        </MarketingSection>

        <MarketingSection eyebrow="FAQ" title="Questions, answered" className="border-b">
          <div className="mx-auto max-w-2xl divide-y rounded-2xl border bg-card">
            {FAQ.map(({ q, a }) => (
              <details key={q} className="group px-5">
                <summary className="flex cursor-pointer list-none items-center justify-between gap-4 py-4 font-medium [&::-webkit-details-marker]:hidden">
                  {q}
                  <Plus className="size-4 shrink-0 text-muted-foreground transition-transform duration-200 group-open:rotate-45" />
                </summary>
                <p className="pb-4 text-sm text-muted-foreground">{a}</p>
              </details>
            ))}
          </div>
        </MarketingSection>

        <CtaBand />
      </main>
      <SiteFooter />
    </div>
  );
}
