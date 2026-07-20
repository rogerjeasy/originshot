import type { Metadata } from "next";
import Link from "next/link";
import { ArrowRight, ShieldCheck } from "lucide-react";

import { ClosingCta } from "@/components/landing/closing-cta";
import { LandingFooter } from "@/components/landing/landing-footer";
import { LandingHeader } from "@/components/landing/landing-header";
import { Reveal, SectionHead } from "@/components/landing/section";

export const metadata: Metadata = {
  title: "About · OriginShot",
  description:
    "Why OriginShot exists: studio-grade product catalogs from one phone photo, with cryptographic proof of what's real and what's AI.",
};

/**
 * Home shows the proof; how-it-works explains the machine; this page states the
 * position. So it is prose-first and single-column at the top, where the other
 * two open on a split — an about page that opens on a stat grid is a pitch deck
 * wearing an essay's title.
 *
 * The principles section is the part most easily written as decoration. Each one
 * here carries the thing that enforces it in mono underneath, because the
 * system's own rule is that sans is what we claim and mono is what can be
 * checked. A principle with nothing checkable under it was cut rather than
 * padded.
 */

const PRINCIPLES = [
  {
    claim: "The photograph outranks the interface",
    body: "Generated media is the reason anyone is here, so it is framed like an object on a table — inset hairline, cast shadow, locked aspect — and never cropped to fit a card that wanted to be square.",
    enforced: ".plate / .frame · aspect locked per style",
  },
  {
    claim: "Provenance is not a footnote",
    body: "Every output carries a manifest naming the model that made it and the original it came from, written into the file's own bytes. Re-encoding the image breaks the seal rather than quietly surviving it.",
    enforced: "XMP manifest · content-bound to the pixels",
  },
  {
    claim: "The boring parts are the product",
    body: "Auth is enforced on every route with no development bypass, accounts are isolated, and credit is held against a ceiling then settled against what the provider actually billed. None of it demos well. All of it is why this is a tool and not a toy.",
    enforced: "no dev bypass · holds settled at real cost",
  },
  {
    claim: "Say what fails",
    body: "One step in the pipeline has no fallback configured today, and the how-it-works page names it. A product page that only describes the happy path is describing a demo.",
    enforced: "partial runs bill only what landed",
  },
];

// Figures are derived from backend/app/pricing.py (`_OUTPUTS`, `_ETA_SECONDS`);
// model IDs from originshot_pipelines/registry.py. Nothing aspirational here.
const BUILD = [
  ["Backblaze B2", "Every byte the product owns — originals, masters, renditions, manifests, and the transparency log's published checkpoints."],
  ["Genblaze", "One Pipeline API across providers. Each step reports its real cost back, which is what the credit ledger debits."],
  ["gemini-3-pro-image-preview", "Source photo → studio, lifestyle, on-model and variant frames."],
  ["Kling-Image2Video-V2.1-Master", "Studio frame → a five-second product video, with i2v fallbacks behind it."],
];

export default function AboutPage() {
  return (
    <div className="band-ink min-h-dvh">
      <LandingHeader />

      <main>
        {/* ── The position ───────────────────────────────────────────────── */}
        <section className="viewing-light relative overflow-hidden">
          <div className="relative mx-auto max-w-[1320px] px-5 pb-20 pt-12 sm:px-8 sm:pb-24 sm:pt-20">
            <div className="max-w-3xl">
              <p className="kicker t-accent">About OriginShot</p>
              <h1 className="display-face mt-5 text-[clamp(2.5rem,5.6vw,4.25rem)]">
                Studio-grade catalogs, honest about what&apos;s real.
              </h1>
              <p className="on-ink-mute mt-7 text-pretty text-[17.5px] leading-relaxed">
                Good product photography decides whether a listing sells or gets scrolled past —
                and for millions of small sellers it means renting a studio, booking a model, and
                re-shooting every colourway. Meanwhile generated imagery is filling the same
                marketplaces with no way for a buyer to tell which is which.
              </p>
              <p className="mt-5 text-pretty text-[17.5px] leading-relaxed">
                OriginShot answers both at once: one phone photo becomes a full marketplace pack,
                and every frame leaves with a record you can check without taking our word for it.
              </p>

              <div className="mt-10 flex flex-col gap-3 sm:flex-row">
                <Link
                  href="/studio"
                  className="btn-tungsten inline-flex h-12 items-center justify-center gap-2 rounded-lg px-7 text-[15px] font-semibold"
                >
                  Start free
                  <ArrowRight className="size-4" />
                </Link>
                <Link
                  href="/how-it-works"
                  className="btn-on-ink inline-flex h-12 items-center justify-center gap-2 rounded-lg px-7 text-[15px] font-medium"
                >
                  How it works
                </Link>
              </div>
            </div>
          </div>
        </section>

        {/* ── Principles ─────────────────────────────────────────────────── */}
        <section className="band-paper">
          <div className="mx-auto max-w-[1320px] px-5 py-20 sm:px-8 sm:py-28">
            <Reveal>
              <SectionHead
                kicker="Principles"
                title="What we optimise for"
                lede="Four positions the product is actually held to. Each one is followed by the mechanism that enforces it — a principle you can't check is a slogan."
              />
            </Reveal>

            <Reveal delay={0.06}>
              <ol className="mt-14 grid gap-x-16 gap-y-12 lg:grid-cols-2">
                {PRINCIPLES.map((p, i) => (
                  <li key={p.claim} className="min-w-0 border-t pt-6">
                    <span className="display-face on-paper-mute block text-[2rem] leading-none">
                      {String(i + 1).padStart(2, "0")}
                    </span>
                    <h3 className="mt-4 text-[1.3rem] font-semibold tracking-[-0.025em]">
                      {p.claim}
                    </h3>
                    <p className="on-paper-mute mt-3 text-[15.5px] leading-relaxed">{p.body}</p>
                    <p className="t-verify mt-5 flex items-start gap-2 font-mono text-[12px] leading-relaxed [overflow-wrap:anywhere]">
                      <ShieldCheck className="mt-px size-3.5 shrink-0" aria-hidden />
                      <span className="min-w-0">{p.enforced}</span>
                    </p>
                  </li>
                ))}
              </ol>
            </Reveal>
          </div>
        </section>

        {/* ── What it's built on ─────────────────────────────────────────── */}
        <section className="band-ink">
          <div className="mx-auto max-w-[1320px] px-5 py-20 sm:px-8 sm:py-28">
            <Reveal>
              <SectionHead
                tone="ink"
                kicker="The stack"
                title="Generate with Genblaze. Store on Backblaze B2."
                lede="Built for the Backblaze Generative Media Hackathon — to show how AI media moves from prompt, to pipeline, to durable storage, without losing track of where any of it came from."
              />
            </Reveal>

            <Reveal delay={0.06}>
              <dl
                className="mt-14 grid gap-px overflow-hidden rounded-xl border"
                style={{ backgroundColor: "var(--ink-line)" }}
              >
                {BUILD.map(([name, role]) => (
                  <div
                    key={name}
                    className="grid gap-2 p-6 sm:grid-cols-[minmax(0,18rem)_minmax(0,1fr)] sm:items-baseline sm:gap-8"
                    style={{ backgroundColor: "var(--ink-2)" }}
                  >
                    <dt className="t-verify min-w-0 font-mono text-[13px] [overflow-wrap:anywhere]">
                      {name}
                    </dt>
                    <dd className="on-ink-mute min-w-0 text-[15px] leading-relaxed">{role}</dd>
                  </div>
                ))}
              </dl>
            </Reveal>
          </div>
        </section>

        <ClosingCta />
      </main>

      <LandingFooter />
    </div>
  );
}
