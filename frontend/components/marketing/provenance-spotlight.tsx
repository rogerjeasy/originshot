import Link from "next/link";
import { ArrowRight, Link2, ScanLine, ShieldCheck } from "lucide-react";

import { DEMO_ASSETS } from "@/lib/demo-assets";
import { buttonVariants } from "@/components/ui/button";
import { Section } from "./section";

const CLAIMS = [
  {
    icon: ShieldCheck,
    title: "Every asset is hashed",
    body: "The SHA-256 of the bytes is recorded as the asset is written. Nothing is trusted on the strength of a filename.",
  },
  {
    icon: Link2,
    title: "Generated frames point home",
    body: "A manifest ties each output back to the authentic original it came from, so the lineage of any image is a lookup rather than a guess.",
  },
  {
    icon: ScanLine,
    title: "Tampering shows up",
    body: "Provenance is content-bound. Re-encode or edit the pixels and verification fails loudly instead of quietly passing.",
  },
];

/**
 * The trust argument, anchored to a real asset. The hash below belongs to an
 * actual object in B2 and the link resolves — a visitor can check the claim
 * before signing up, which is a far stronger version of this section than a
 * diagram of one.
 */
export function ProvenanceSpotlight() {
  const sample = DEMO_ASSETS.find((a) => a.slot === "studio-01") ?? DEMO_ASSETS[0];

  return (
    <div className="border-y bg-card">
      <Section
        eyebrow="Provenance"
        title="Buyers can tell what's real. So can marketplaces."
        description="AI product imagery is heading for disclosure rules, and platforms already ask sellers to declare it. OriginShot answers that with a checkable record instead of a checkbox."
      >
        <div className="mt-12 grid gap-10 lg:grid-cols-[1fr_minmax(0,400px)] lg:gap-16">
          <ul className="grid content-start gap-8 sm:grid-cols-3 lg:grid-cols-1 lg:gap-7">
            {CLAIMS.map(({ icon: Icon, title, body }) => (
              <li key={title} className="flex gap-4">
                <span className="mt-0.5 grid size-9 shrink-0 place-items-center rounded-md border bg-background text-verified">
                  <Icon className="size-4" />
                </span>
                <div className="min-w-0">
                  <h3 className="text-[15px] font-semibold tracking-tight">{title}</h3>
                  <p className="mt-1 text-sm text-muted-foreground">{body}</p>
                </div>
              </li>
            ))}
          </ul>

          {/* A certificate, not a diagram. */}
          <figure className="min-w-0 self-start overflow-hidden rounded-lg border bg-background shadow-raised">
            <figcaption className="flex items-center justify-between gap-2 border-b bg-muted/60 px-4 py-2.5">
              <span className="label-mono text-muted-foreground">Provenance record</span>
              <span className="label-mono inline-flex items-center gap-1.5 text-verified">
                <ShieldCheck className="size-3" />
                Verified
              </span>
            </figcaption>

            <dl className="divide-y font-mono text-xs">
              {[
                ["sha256", sample.sha],
                ["style", sample.style],
                ["provider", "genblaze"],
                ["model", "gemini-3-pro-image-preview"],
                ["dimensions", `${sample.width}×${sample.height}`],
                ["content_bound", "true"],
                ["disclosure", "AI-generated"],
              ].map(([k, v]) => (
                <div key={k} className="grid grid-cols-[7rem_minmax(0,1fr)] gap-3 px-4 py-2.5">
                  <dt className="truncate text-muted-foreground">{k}</dt>
                  <dd className="min-w-0 truncate text-foreground" title={v}>
                    {v}
                  </dd>
                </div>
              ))}
            </dl>

            <div className="border-t bg-muted/40 p-3">
              <Link
                href={`/verify/${sample.sha}`}
                className={`${buttonVariants({ variant: "outline", size: "sm" })} w-full`}
              >
                Check this hash yourself <ArrowRight />
              </Link>
            </div>
          </figure>
        </div>
      </Section>
    </div>
  );
}
