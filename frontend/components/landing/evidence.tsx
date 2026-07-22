import Link from "next/link";
import { ArrowRight, Fingerprint, GitBranch, ScanLine, ShieldCheck } from "lucide-react";

import { DEMO_ASSETS } from "@/lib/demo-assets";
import { Reveal, SectionHead } from "./section";

const CLAIMS = [
  {
    icon: Fingerprint,
    title: "Every asset is hashed as it lands",
    body: "The SHA-256 of the bytes is recorded at write time. Nothing is trusted on the strength of a filename.",
  },
  {
    icon: GitBranch,
    title: "Generated frames point home",
    body: "A manifest ties each output back to the authentic original it came from, so the lineage of any image is a lookup rather than a guess.",
  },
  {
    icon: ScanLine,
    title: "Tampering shows up",
    body: "Provenance is content-bound. Re-encode or repaint the pixels and verification fails loudly instead of quietly passing.",
  },
];

const ROUTES = [
  {
    href: "/check",
    label: "Check a listing",
    body: "Paste a listing link — we recognise the photo even after a re-encode.",
  },
  { href: "/verify", label: "Verify a file", body: "Drop in any image and get its record back." },
  {
    href: "/ledger",
    label: "Transparency log",
    body: "An append-only hash chain, checkpointed into B2.",
  },
  {
    href: "/resolve",
    label: "Resolve a dispute",
    body: "Compare a delivered item against what was listed.",
  },
];

/**
 * The trust argument, anchored to an asset a visitor can check right now. The
 * hash below belongs to a real object in B2 and the link resolves, so the claim
 * is testable before signing up — a much stronger version of this section than
 * a diagram of one.
 */
export function Evidence() {
  const sample = DEMO_ASSETS.find((a) => a.slot === "studio-01") ?? DEMO_ASSETS[0];

  return (
    <section className="band-paper">
      <div className="mx-auto max-w-[1320px] px-5 py-20 sm:px-8 sm:py-28">
        <Reveal>
          <SectionHead
            kicker="Evidence"
            title="Anyone can check what's real. Including your buyer."
            lede="AI product imagery is heading for disclosure rules, and platforms already ask sellers to declare it. OriginShot answers with a record that resolves, not a checkbox that doesn't."
          />
        </Reveal>

        <div className="mt-14 grid gap-12 lg:grid-cols-[1fr_minmax(0,420px)] lg:gap-16">
          <Reveal delay={0.06}>
            <ul className="grid content-start gap-9">
              {CLAIMS.map(({ icon: Icon, title, body }) => (
                <li key={title} className="flex gap-5">
                  <span
                    className="t-verify mt-0.5 grid size-10 shrink-0 place-items-center rounded-lg border"
                    style={{ backgroundColor: "var(--paper-2)" }}
                  >
                    <Icon className="size-[18px]" />
                  </span>
                  <div className="min-w-0">
                    <h3 className="text-[16px] font-semibold tracking-[-0.02em]">{title}</h3>
                    <p className="on-paper-mute mt-1.5 text-[14.5px] leading-relaxed">{body}</p>
                  </div>
                </li>
              ))}
            </ul>

            <div className="mt-11 grid gap-px overflow-hidden rounded-xl border sm:grid-cols-2">
              {ROUTES.map((r) => (
                <Link
                  key={r.href}
                  href={r.href}
                  className="group flex flex-col gap-1.5 p-5 transition-colors"
                  style={{ backgroundColor: "var(--paper-2)" }}
                >
                  <span className="flex items-center justify-between gap-2 text-[14.5px] font-semibold tracking-[-0.02em]">
                    {r.label}
                    <ArrowRight className="size-4 shrink-0 transition-transform duration-200 group-hover:translate-x-0.5" />
                  </span>
                  <span className="on-paper-mute text-[13px] leading-snug">{r.body}</span>
                </Link>
              ))}
            </div>
          </Reveal>

          {/* A certificate, not a diagram. */}
          <Reveal delay={0.12}>
            <figure
              className="min-w-0 self-start overflow-hidden rounded-xl border"
              style={{ backgroundColor: "var(--paper-2)" }}
            >
              <figcaption className="flex items-center justify-between gap-2 border-b px-4 py-3">
                <span className="kicker on-paper-mute">Provenance record</span>
                <span className="kicker t-verify inline-flex items-center gap-1.5">
                  <ShieldCheck className="size-3.5" />
                  Verified
                </span>
              </figcaption>

              <dl className="divide-y font-mono text-[12px]">
                {[
                  ["sha256", sample.sha],
                  ["style", sample.style],
                  ["provider", "genblaze · gmicloud"],
                  ["model", "gemini-3-pro-image-preview"],
                  ["dimensions", `${sample.width}×${sample.height}`],
                  ["content_bound", "true"],
                  ["disclosure", "AI-generated"],
                ].map(([k, v]) => (
                  <div key={k} className="grid grid-cols-[7.5rem_minmax(0,1fr)] gap-3 px-4 py-3">
                    <dt className="on-paper-mute truncate">{k}</dt>
                    <dd className="min-w-0 truncate" title={v}>
                      {v}
                    </dd>
                  </div>
                ))}
              </dl>

              <div className="border-t p-3">
                <Link
                  href={`/verify/${sample.sha}`}
                  className="btn-tungsten inline-flex h-10 w-full items-center justify-center gap-2 rounded-md text-[14px] font-semibold"
                >
                  Check this hash yourself
                  <ArrowRight className="size-4" />
                </Link>
              </div>
            </figure>
          </Reveal>
        </div>
      </div>
    </section>
  );
}
