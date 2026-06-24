import Link from "next/link";
import { ArrowRight, FileCheck2, ShieldCheck } from "lucide-react";

import { ProvenanceBadge } from "@/components/provenance-badge";
import { FadeIn } from "@/components/motion/fade-in";
import { buttonVariants } from "@/components/ui/button";
import { MarketingSection } from "./section";

const ROWS = [
  { label: "SHA-256", value: "7f3a…b1c4" },
  { label: "Provider", value: "gmi-cloud" },
  { label: "Model", value: "seedream-3" },
  { label: "Derived from", value: "a1b2…8f90" },
];

/** Trust-layer spotlight — a verify "certificate" beside the pitch, reusing live brand atoms. */
export function ProvenanceSpotlight() {
  return (
    <MarketingSection className="border-b">
      <div className="grid items-center gap-10 lg:grid-cols-2">
        <FadeIn>
          <p className="mb-2 text-sm font-semibold uppercase tracking-wide text-accent">
            Trust, not vibes
          </p>
          <h2 className="text-balance text-2xl font-semibold tracking-tight sm:text-3xl">
            Provenance you can check from the file itself
          </h2>
          <p className="mt-3 text-pretty text-muted-foreground">
            ListSnap embeds a SHA-256 manifest into every generated image and video. Drop any file
            back into Verify and we re-extract the manifest and re-hash the content — proving
            whether it&apos;s an authentic original, an AI generation, or has been tampered with.
          </p>
          <ul className="mt-5 space-y-2 text-sm">
            {[
              "Content-bound — the hash matches the actual bytes, not just metadata",
              "Full lineage back to the authentic source photo",
              "Doubles as AI-disclosure compliance for marketplaces",
            ].map((t) => (
              <li key={t} className="flex items-start gap-2.5">
                <ShieldCheck className="mt-0.5 size-4 shrink-0 text-verified" />
                <span className="text-muted-foreground">{t}</span>
              </li>
            ))}
          </ul>
          <Link href="/verify" className={`${buttonVariants({ variant: "outline" })} mt-6`}>
            Try Verify <ArrowRight />
          </Link>
        </FadeIn>

        <FadeIn delay={0.1} y={16}>
          <div className="relative">
            <div aria-hidden className="glow-verified pointer-events-none absolute -inset-6 -z-10 blur-2xl" />
            <div className="frame-deep overflow-hidden rounded-2xl border bg-card">
              <div className="flex items-center gap-3 border-b bg-verified/5 p-4">
                <span className="grid size-10 place-items-center rounded-xl bg-verified/15">
                  <ShieldCheck className="size-5 text-verified" />
                </span>
                <div>
                  <p className="font-semibold">Integrity verified</p>
                  <p className="text-sm text-muted-foreground">Authentic original</p>
                </div>
                <span className="ms-auto inline-flex items-center gap-1.5 rounded-full bg-verified/12 px-2.5 py-1 text-xs font-medium text-verified">
                  <FileCheck2 className="size-3.5" /> Content-bound
                </span>
              </div>
              <dl className="grid grid-cols-2 gap-x-4 gap-y-3 p-5 text-sm">
                {ROWS.map((r) => (
                  <div key={r.label} className="flex flex-col gap-0.5">
                    <dt className="text-xs text-muted-foreground">{r.label}</dt>
                    <dd className="truncate font-mono text-xs">{r.value}</dd>
                  </div>
                ))}
              </dl>
              <div className="flex items-center justify-between gap-2 border-t p-4">
                <span className="text-sm font-medium">Generated studio shot</span>
                <ProvenanceBadge authentic={false} sha="a1b2c3d4e5f60718293a4b5c6d7e8f90" />
              </div>
            </div>
          </div>
        </FadeIn>
      </div>
    </MarketingSection>
  );
}
