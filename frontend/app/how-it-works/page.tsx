import type { Metadata } from "next";
import Link from "next/link";
import { Plus, ShieldCheck } from "lucide-react";

import { CtaBand } from "@/components/marketing/cta-band";
import { MarketingHeader } from "@/components/marketing/marketing-header";
import { MarketingPageHero } from "@/components/marketing/page-hero";
import { PipelineFlow } from "@/components/marketing/pipeline-flow";
import { Pipeline } from "@/components/marketing/pipeline";
import { ProvenanceSpotlight } from "@/components/marketing/provenance-spotlight";
import { Section } from "@/components/marketing/section";
import { TrustStrip } from "@/components/marketing/trust-strip";
import { FadeIn } from "@/components/motion/fade-in";
import { SiteFooter } from "@/components/site-footer";
import { buttonVariants } from "@/components/ui/button";

export const metadata: Metadata = {
  title: "How it works · OriginShot",
  description:
    "From one phone photo to a verified, marketplace-ready pack — the OriginShot pipeline, step by step.",
};

/**
 * Answers are written against the code, not the pitch. Several of these used to
 * claim providers that aren't wired (OpenAI, Luma, Imagen/Veo) and models that
 * aren't used (Seedream, FLUX, Seedance). If the registry or pricing table
 * changes, these change with them.
 */
const FAQ = [
  {
    q: "Do I need a real product shoot?",
    a: "No. A single ordinary phone photo is enough. OriginShot treats it as the authentic source and builds the rest of the catalog around it.",
  },
  {
    q: "What does “provenance-verified” actually mean?",
    a: "Every generated file carries an embedded, content-bound SHA-256 manifest. Drop the file back on the Verify page and we re-hash the bytes and re-read the manifest — proving whether it's an authentic original, an AI generation, or has been altered since it left us.",
  },
  {
    q: "Which models does it actually use?",
    a: "Images — studio, lifestyle, on-model, and variants — all run on gemini-3-pro-image-preview, orchestrated by Genblaze and served through GMI Cloud. Video runs on Kling-Image2Video-V2.1-Master, falling back to pixverse-v5.6-i2v and then wan2.6-r2v. The exact model that produced a file is recorded in its manifest, so you never have to trust this page.",
  },
  {
    q: "What happens if a model fails?",
    a: "Video has a fallback chain and will retry down it. Image generation currently has no fallback configured — if that step fails, the job finishes partial and you're only charged for what was produced.",
  },
  {
    q: "How much does one pack cost to generate?",
    a: "A full pack is seven outputs: one studio shot, two lifestyle scenes, one on-model image, two variants, and one video. Images are metered at $0.04 each and video at $0.50, so a complete run is about $0.74 of provider cost.",
  },
  {
    q: "What happens to the photo I upload?",
    a: "It's validated, re-encoded to strip EXIF and GPS, hashed, and stored as your authentic original. Files you drop on the Verify page are different — those are read in memory to check them and never persisted.",
  },
  {
    q: "Where are my assets stored?",
    a: "On Backblaze B2 — durable, S3-compatible object storage, isolated per account. Storage is content-addressable, so identical bytes are stored exactly once.",
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
          description="No studio, no shoot, and no guesswork about what's real. Here's exactly what happens between your one photo and a marketplace-ready catalog."
        >
          <Link href="/studio" className={buttonVariants({ variant: "accent", size: "lg" })}>
            Try it free
          </Link>
          <Link href="/verify" className={buttonVariants({ variant: "outline", size: "lg" })}>
            <ShieldCheck /> Verify a file
          </Link>
        </MarketingPageHero>

        <Pipeline />

        <div className="border-y bg-card">
          <Section
            eyebrow="Inside the run"
            title="One photo, one image model, four framings"
            description="The pipeline reads your product once and reuses that reading for every image style — which is why the object stays consistent instead of drifting between shots."
          >
            <FadeIn className="mt-10">
              <PipelineFlow />
            </FadeIn>
            <p className="mt-6 max-w-2xl text-sm text-muted-foreground">
              These are the real model identifiers from the pipeline registry, and the one that
              produced any given file is written into its manifest — so you can check a specific
              asset rather than taking this diagram's word for it.
            </p>
          </Section>
        </div>

        <ProvenanceSpotlight />

        <Section
          eyebrow="The stack"
          title="Generate with Genblaze. Store on Backblaze B2."
          description="Genblaze chains and swaps models without rebuilding pipeline logic. B2 holds every image, video, manifest, and analytics record, content-addressed so duplicates cost nothing."
        >
          <div className="mt-10">
            <TrustStrip />
          </div>
        </Section>

        <div className="border-t bg-card">
          <Section eyebrow="FAQ" title="Questions, answered">
            <div className="mt-10 max-w-2xl divide-y rounded-lg border bg-background">
              {FAQ.map(({ q, a }) => (
                <details key={q} className="group px-5">
                  <summary className="flex cursor-pointer list-none items-center justify-between gap-4 py-4 text-[15px] font-medium [&::-webkit-details-marker]:hidden">
                    {q}
                    <Plus className="size-4 shrink-0 text-muted-foreground transition-transform duration-200 group-open:rotate-45" />
                  </summary>
                  <p className="pb-4 text-sm text-muted-foreground">{a}</p>
                </details>
              ))}
            </div>
          </Section>
        </div>

        <CtaBand />
      </main>
      <SiteFooter />
    </div>
  );
}
