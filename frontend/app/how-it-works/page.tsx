import type { Metadata } from "next";
import Link from "next/link";
import { ArrowRight, ShieldCheck } from "lucide-react";

import { ClosingCta } from "@/components/landing/closing-cta";
import { LandingFooter } from "@/components/landing/landing-footer";
import { LandingHeader } from "@/components/landing/landing-header";
import { Reveal, SectionHead } from "@/components/landing/section";
import { Faq } from "@/components/how-it-works/faq";
import { RunLedger } from "@/components/how-it-works/run-ledger";

export const metadata: Metadata = {
  title: "How it works · OriginShot",
  description:
    "What actually happens between your one phone photo and a verified, marketplace-ready pack — the models, the storage, the costs, and what happens when a step fails.",
};

/**
 * The landing page argues; this page explains. So it is built as a document
 * rather than a pitch: one real run, entered stage by stage, followed by the
 * things a seller asks next — what's in the pack, what we keep, what happens
 * when something breaks.
 *
 * The failure section is deliberate. Most product pages hide this, and hiding it
 * is what makes a tool read as a demo. Naming the one step with no fallback, and
 * what it costs you when it trips, is the strongest available evidence that the
 * pipeline is real.
 */

// Both derived from backend/app/pricing.py — `_OUTPUTS` and `_ETA_SECONDS`.
const SUMMARY = [
  ["in", "1 photo"],
  ["out", "7 assets"],
  ["time", "~5 min"],
  ["cost", "$0.74 est."],
];

const PACK = [
  ["studio", "1", "White-background frames that clear Amazon and eBay main-image rules."],
  ["lifestyle", "2", "The product in a room a buyer recognises — the frame that earns the click."],
  ["on-model", "1", "Held or worn, so scale reads instantly."],
  ["variants", "2", "Colour and angle sweeps for products sold in more than one finish."],
  ["video", "1", "A five-second product video, generated from the studio frame."],
];

const KEPT = [
  ["Your authentic original", "Hashed on arrival and never overwritten. Everything else points back to it."],
  ["Masters and renditions", "One master per frame, plus a correctly sized copy per marketplace preset."],
  ["Provenance manifests", "The record a /verify lookup resolves against."],
  ["Transparency checkpoints", "Published heads of the append-only hash chain."],
];

const NOT_KEPT = [
  ["EXIF and GPS", "Stripped by re-encoding before your photo is stored. Your kitchen doesn't ship with the picture."],
  ["Files you verify", "Read in memory to check them, then dropped. Verifying a photo doesn't upload it."],
  ["Duplicate bytes", "Storage is content-addressable, so identical files are stored exactly once."],
];

// `cost` is a stamp, not a sentence — it sits in a narrow right-hand column in
// wide tracked caps, where anything longer than three words wraps mid-phrase.
const FAILURES = [
  {
    when: "A video model is down",
    then: "The run falls back down the chain — pixverse-v5.6-i2v, then wan2.6-r2v — before it gives up.",
    cost: "Retries are free",
  },
  {
    when: "The image model fails",
    then: "There is no fallback configured for image editing today, so the job finishes partial rather than pretending. Frames that did land stay in your library.",
    cost: "You pay for what landed",
  },
  {
    when: "A run costs less than quoted",
    then: "Credit is held against a ceiling estimate before the run, then settled against what the provider actually billed.",
    cost: "Difference refunded",
  },
  {
    when: "A run produces nothing",
    then: "The whole hold is released.",
    cost: "Nothing charged",
  },
];

export default function HowItWorksPage() {
  return (
    <div className="band-ink min-h-dvh">
      <LandingHeader />

      <main>
        {/* ── The brief ──────────────────────────────────────────────────── */}
        <section className="viewing-light relative overflow-hidden">
          <div className="relative mx-auto max-w-[1320px] px-5 pb-20 pt-12 sm:px-8 sm:pb-24 sm:pt-20">
            <div className="grid gap-12 lg:grid-cols-[minmax(0,1fr)_minmax(0,22rem)] lg:items-end lg:gap-16">
              <div className="max-w-2xl">
                <p className="kicker t-accent">How it works</p>
                <h1 className="display-face mt-5 text-[clamp(2.5rem,5.6vw,4rem)]">
                  What happens to your photo.
                </h1>
                <p className="on-ink-mute mt-6 text-pretty text-[17px] leading-relaxed">
                  No studio, no shoot, and no guessing about what&apos;s real. Below is one
                  complete run — the same one that produced the frames on the home page —
                  entered stage by stage, with the models, the storage keys and the costs it
                  actually incurred.
                </p>

                <div className="mt-9 flex flex-col gap-3 sm:flex-row">
                  <Link
                    href="/studio"
                    className="btn-tungsten inline-flex h-12 items-center justify-center gap-2 rounded-lg px-7 text-[15px] font-semibold"
                  >
                    Try it free
                    <ArrowRight className="size-4" />
                  </Link>
                  <Link
                    href="/verify"
                    className="btn-on-ink inline-flex h-12 items-center justify-center gap-2 rounded-lg px-7 text-[15px] font-medium"
                  >
                    <ShieldCheck className="size-4" />
                    Verify a file
                  </Link>
                </div>
              </div>

              {/* The run docket — the whole page in four figures. */}
              <dl
                className="grid grid-cols-2 gap-px overflow-hidden rounded-xl border"
                style={{ backgroundColor: "var(--ink-line)" }}
              >
                {SUMMARY.map(([k, v]) => (
                  <div
                    key={k}
                    className="flex flex-col gap-1.5 p-5"
                    style={{ backgroundColor: "var(--ink-2)" }}
                  >
                    <dt className="kicker on-ink-mute">{k}</dt>
                    <dd className="display-face text-[1.625rem]">{v}</dd>
                  </div>
                ))}
              </dl>
            </div>
          </div>
        </section>

        {/* ── The run ────────────────────────────────────────────────────── */}
        <section className="band-paper">
          <div className="mx-auto max-w-[1320px] px-5 py-20 sm:px-8 sm:py-28">
            <Reveal>
              <SectionHead
                kicker="One run, start to finish"
                title="Five stages, and what each one writes"
                lede="Nothing below is a mock-up stage. Each one writes real objects to Backblaze B2 and appears in the job log while it happens."
              />
            </Reveal>
            <RunLedger />
          </div>
        </section>

        {/* ── What you get ───────────────────────────────────────────────── */}
        <section className="band-ink">
          <div className="mx-auto max-w-[1320px] px-5 py-20 sm:px-8 sm:py-28">
            <Reveal>
              <SectionHead
                tone="ink"
                kicker="The pack"
                title="Seven files, and where each one goes"
                lede="A pack isn't a folder of variations on one shot. It's the set a listing actually needs, in the proportions a listing actually uses them."
              />
            </Reveal>

            <Reveal delay={0.06}>
              <dl className="mt-14 grid gap-px overflow-hidden rounded-xl border" style={{ backgroundColor: "var(--ink-line)" }}>
                {PACK.map(([style, n, use]) => (
                  <div
                    key={style}
                    className="grid gap-2 p-6 sm:grid-cols-[10rem_3rem_minmax(0,1fr)] sm:items-baseline sm:gap-6"
                    style={{ backgroundColor: "var(--ink-2)" }}
                  >
                    <dt className="t-verify font-mono text-[13px]">{style}</dt>
                    <span className="tabular kicker on-ink-mute sm:text-right" aria-hidden>
                      ×{n}
                    </span>
                    <dd className="on-ink-mute min-w-0 text-[15px] leading-relaxed">{use}</dd>
                  </div>
                ))}
              </dl>
            </Reveal>
          </div>
        </section>

        {/* ── Storage and privacy ────────────────────────────────────────── */}
        <section className="band-paper">
          <div className="mx-auto max-w-[1320px] px-5 py-20 sm:px-8 sm:py-28">
            <Reveal>
              <SectionHead
                kicker="Storage"
                title="What we keep, and what we never do."
                lede="Everything the product owns lives in Backblaze B2 under a content-addressable key. The second list matters as much as the first."
              />
            </Reveal>

            <Reveal delay={0.06}>
              <div className="mt-14 grid gap-10 lg:grid-cols-2 lg:gap-16">
                {[
                  { head: "Kept, and durable", rows: KEPT, tone: "verify" as const },
                  { head: "Never kept", rows: NOT_KEPT, tone: "accent" as const },
                ].map(({ head, rows, tone }) => (
                  <div key={head} className="min-w-0">
                    <h3 className={`kicker ${tone === "verify" ? "t-verify" : "t-accent"}`}>
                      {head}
                    </h3>
                    <dl className="mt-6 grid gap-6">
                      {rows.map(([k, v]) => (
                        <div key={k} className="border-t pt-4">
                          <dt className="text-[15.5px] font-semibold tracking-[-0.02em]">{k}</dt>
                          <dd className="on-paper-mute mt-1.5 text-[14.5px] leading-relaxed">{v}</dd>
                        </div>
                      ))}
                    </dl>
                  </div>
                ))}
              </div>
            </Reveal>
          </div>
        </section>

        {/* ── Failure modes ──────────────────────────────────────────────── */}
        <section className="band-ink">
          <div className="mx-auto max-w-[1320px] px-5 py-20 sm:px-8 sm:py-28">
            <Reveal>
              <SectionHead
                tone="ink"
                kicker="When it doesn't work"
                title="Model providers go down. Here's what that costs you."
                lede="Generative pipelines fail more often than product pages admit. These are the real behaviours, including the one step that has no fallback today."
              />
            </Reveal>

            <Reveal delay={0.06}>
              <ul className="mt-14 grid gap-px overflow-hidden rounded-xl border" style={{ backgroundColor: "var(--ink-line)" }}>
                {FAILURES.map((f) => (
                  <li
                    key={f.when}
                    className="grid gap-3 p-6 lg:grid-cols-[15rem_minmax(0,1fr)_11rem] lg:items-baseline lg:gap-8"
                    style={{ backgroundColor: "var(--ink-2)" }}
                  >
                    <h3 className="text-[15.5px] font-semibold tracking-[-0.02em]">{f.when}</h3>
                    <p className="on-ink-mute min-w-0 text-[14.5px] leading-relaxed">{f.then}</p>
                    <p className="t-verify kicker lg:text-right">{f.cost}</p>
                  </li>
                ))}
              </ul>
            </Reveal>
          </div>
        </section>

        {/* ── FAQ ────────────────────────────────────────────────────────── */}
        <section className="band-paper">
          <div className="mx-auto max-w-[1320px] px-5 py-20 sm:px-8 sm:py-28">
            <Reveal>
              <SectionHead kicker="Questions" title="Answered against the code" />
            </Reveal>
            <Reveal delay={0.06}>
              <Faq />
            </Reveal>
          </div>
        </section>

        <ClosingCta />
      </main>

      <LandingFooter />
    </div>
  );
}
