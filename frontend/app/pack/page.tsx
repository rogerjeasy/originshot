import type { Metadata } from "next";
import Link from "next/link";
import { ArrowRight, ShieldCheck } from "lucide-react";

import { ClosingCta } from "@/components/landing/closing-cta";
import { LandingFooter } from "@/components/landing/landing-footer";
import { LandingHeader } from "@/components/landing/landing-header";
import { Reveal, SectionHead } from "@/components/landing/section";
import { PackSheet } from "@/components/pack/pack-sheet";
import { PACK_COMPOSITION, allFrames } from "@/lib/pack";

export const metadata: Metadata = {
  title: "A real pack · OriginShot",
  description:
    "Every frame a real OriginShot run produced from a single phone photo — studio, lifestyle, in-context, in-hand and video — each one carrying a SHA-256 you can check against the provenance ledger.",
};

/**
 * The landing gallery makes the claim; this page is the exhibit. It exists as a
 * real route rather than a #pack anchor because it is the link people send each
 * other and the link the hero's second button points at — an anchor into the
 * middle of a marketing page can't carry its own title, its own metadata, or a
 * scroll position that survives being shared.
 *
 * Everything numeric below is derived: the sheet count from lib/pack, the pack
 * composition from backend/app/pricing.py `_OUTPUTS`, and the cost and ETA from
 * `estimate_styles()` / `_ETA_SECONDS` for all five styles. Keep them in step if
 * the cost model moves.
 */
const PACK_OUTPUTS = PACK_COMPOSITION.reduce((n, r) => n + r.outputs, 0);

const PROOF = [
  {
    head: "Every frame is hashed",
    body: "A SHA-256 is taken over the bytes at the moment the frame is written to Backblaze B2, and a provenance manifest records the model, the prompt and the source photo it derives from.",
    href: "/verify",
    cta: "Verify a file",
  },
  {
    head: "The record is append-only",
    body: "Manifests are entered into a hash chain whose heads are published as checkpoints. A record can't be edited after the fact without breaking every entry that followed it.",
    href: "/ledger",
    cta: "Read the transparency log",
  },
  {
    head: "A buyer can check it without an account",
    body: "If someone claims a listing photo isn't the product they received, the evidence report is a public URL. No login, and the photo they send is never stored.",
    href: "/resolve",
    cta: "Resolve a dispute",
  },
];

export default function PackPage() {
  const sheetCount = allFrames().length;

  const DOCKET: [string, string][] = [
    ["source", "1 photo"],
    ["on this sheet", `${sheetCount} frames`],
    ["one pack", `${PACK_OUTPUTS} assets`],
    ["cost", "$0.74 est."],
  ];

  return (
    <div className="band-ink min-h-dvh">
      <LandingHeader />

      <main>
        {/* ── The exhibit label ──────────────────────────────────────────── */}
        <section className="viewing-light relative overflow-hidden">
          <div className="relative mx-auto max-w-[1320px] px-5 pb-20 pt-12 sm:px-8 sm:pb-24 sm:pt-20">
            <div className="grid gap-12 lg:grid-cols-[minmax(0,1fr)_minmax(0,22rem)] lg:items-end lg:gap-16">
              <div className="max-w-2xl">
                <p className="kicker t-accent">A real pack</p>
                <h1 className="display-face mt-5 text-[clamp(2.5rem,5.6vw,4rem)]">
                  One photo of a mug.
                  <br />
                  <span className="on-ink-mute">Everything else on this page.</span>
                </h1>
                <p className="on-ink-mute mt-6 text-pretty text-[17px] leading-relaxed">
                  These are not renders of what OriginShot might produce. Every frame below came
                  out of one run, from one phone photo, and still sits in the Backblaze B2 bucket
                  it was written to. Open any of them and you get the hash — paste it into{" "}
                  <span className="font-mono">/verify</span> and the record answers.
                </p>

                <div className="mt-9 flex flex-col gap-3 sm:flex-row">
                  <Link
                    href="/studio"
                    className="btn-tungsten inline-flex h-12 items-center justify-center gap-2 rounded-lg px-7 text-[15px] font-semibold"
                  >
                    Generate your own
                    <ArrowRight className="size-4" />
                  </Link>
                  <Link
                    href="/how-it-works"
                    className="btn-on-ink inline-flex h-12 items-center justify-center gap-2 rounded-lg px-7 text-[15px] font-medium"
                  >
                    <ShieldCheck className="size-4" />
                    How the run works
                  </Link>
                </div>
              </div>

              <dl
                className="grid grid-cols-2 gap-px overflow-hidden rounded-xl border"
                style={{ backgroundColor: "var(--ink-line)" }}
              >
                {DOCKET.map(([k, v]) => (
                  <div
                    key={k}
                    className="flex flex-col gap-1.5 p-5"
                    style={{ backgroundColor: "var(--ink-2)" }}
                  >
                    <dt className="kicker on-ink-mute">{k}</dt>
                    <dd className="display-face text-[1.5rem]">{v}</dd>
                  </div>
                ))}
              </dl>
            </div>
          </div>
        </section>

        {/* ── The sheet ──────────────────────────────────────────────────── */}
        <section className="band-paper">
          <div className="mx-auto max-w-[1320px] px-5 py-20 sm:px-8 sm:py-28">
            <Reveal>
              <SectionHead
                kicker="Contact sheet"
                title="Every frame the run returned."
                lede="Grouped by where a seller actually puts the picture, not by which model made it. Click any frame to inspect its dimensions, its model and its hash."
              />
            </Reveal>

            <Reveal delay={0.06} className="mt-12">
              <PackSheet />
            </Reveal>
          </div>
        </section>

        {/* ── What a pack contains ───────────────────────────────────────── */}
        <section className="band-ink">
          <div className="mx-auto max-w-[1320px] px-5 py-20 sm:px-8 sm:py-28">
            <Reveal>
              <SectionHead
                tone="ink"
                kicker="Composition"
                title={`${PACK_OUTPUTS} assets, and the model behind each`}
                lede="The sheet above is grouped by destination. The pipeline itself has five styles, and this is what one run of all five costs you in outputs — a pack is the set a listing needs, in the proportions a listing uses them."
              />
            </Reveal>

            <Reveal delay={0.06}>
              <dl
                className="mt-14 grid gap-px overflow-hidden rounded-xl border"
                style={{ backgroundColor: "var(--ink-line)" }}
              >
                {PACK_COMPOSITION.map((row) => (
                  <div
                    key={row.style}
                    className="grid gap-2 p-6 lg:grid-cols-[9rem_3rem_minmax(0,1fr)_17rem] lg:items-baseline lg:gap-6"
                    style={{ backgroundColor: "var(--ink-2)" }}
                  >
                    <dt className="t-verify font-mono text-[13px]">{row.style}</dt>
                    <span className="tabular kicker on-ink-mute lg:text-right" aria-hidden>
                      ×{row.outputs}
                    </span>
                    <dd className="on-ink-mute min-w-0 text-[15px] leading-relaxed">{row.use}</dd>
                    <span className="on-ink-mute min-w-0 truncate font-mono text-[12px] lg:text-right">
                      {row.model}
                    </span>
                  </div>
                ))}
              </dl>
            </Reveal>

            <Reveal delay={0.1}>
              <p className="on-ink-mute mt-6 max-w-2xl text-[13.5px] leading-relaxed">
                The demo mug ships in a single finish, so its run had no colour sweep to do and
                the variant slots came back empty — which is why the sheet above holds{" "}
                {sheetCount} frames rather than a neat multiple of {PACK_OUTPUTS}. Costs are
                estimated from provider list prices; what you are actually debited is the figure
                the provider bills, and the difference is refunded.
              </p>
            </Reveal>
          </div>
        </section>

        {/* ── Why you can believe the sheet ──────────────────────────────── */}
        <section className="band-paper">
          <div className="mx-auto max-w-[1320px] px-5 py-20 sm:px-8 sm:py-28">
            <Reveal>
              <SectionHead
                kicker="Provenance"
                title="A gallery is a claim. A hash is a check."
                lede="Anyone can put generated pictures on a page and say they came from one photo. The reason you don't have to take this page's word for it is that each frame carries a record you can resolve independently."
              />
            </Reveal>

            <Reveal delay={0.06}>
              <div className="mt-14 grid gap-10 md:grid-cols-3 md:gap-8">
                {PROOF.map((p) => (
                  <div key={p.head} className="flex min-w-0 flex-col border-t pt-5">
                    <h3 className="text-[16px] font-semibold tracking-[-0.02em]">{p.head}</h3>
                    <p className="on-paper-mute mt-2.5 flex-1 text-[14.5px] leading-relaxed">
                      {p.body}
                    </p>
                    <Link
                      href={p.href}
                      className="t-accent mt-5 inline-flex items-center gap-1.5 text-[14px] font-medium"
                    >
                      {p.cta}
                      <ArrowRight className="size-3.5" />
                    </Link>
                  </div>
                ))}
              </div>
            </Reveal>
          </div>
        </section>

        <ClosingCta />
      </main>

      <LandingFooter />
    </div>
  );
}
