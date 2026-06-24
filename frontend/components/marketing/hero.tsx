import Link from "next/link";
import { ArrowRight, ShieldCheck, Wand2 } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { buttonVariants } from "@/components/ui/button";
import { FadeIn } from "@/components/motion/fade-in";
import { PackShowcase } from "./pack-showcase";

const FIGURES = [
  { value: "1", label: "phone photo in" },
  { value: "12+", label: "assets out" },
  { value: "SHA-256", label: "verified" },
];

/** Marketing hero: editorial headline + the live gallery showcase, on the seamless sweep. */
export function Hero() {
  return (
    <section className="relative overflow-hidden border-b">
      <div aria-hidden className="bg-grid absolute inset-0 -z-10" />
      <div aria-hidden className="glow-cobalt absolute inset-x-0 top-0 -z-10 h-[460px]" />

      <div className="mx-auto grid max-w-7xl items-center gap-12 px-4 py-16 sm:px-6 sm:py-20 lg:grid-cols-2 lg:px-8 lg:py-24">
        <FadeIn>
          <Badge variant="verified" className="mb-5 border border-verified/25 bg-verified/10 px-3 py-1">
            <ShieldCheck /> Provenance-verified by design
          </Badge>
          <h1 className="text-balance text-4xl font-semibold leading-[1.05] tracking-tight sm:text-5xl lg:text-6xl">
            One photo in.
            <br />
            <span className="text-muted-foreground">A full product catalog out.</span>
          </h1>
          <p className="mt-5 max-w-xl text-pretty text-base text-muted-foreground sm:text-lg">
            Snap a single phone photo and ListSnap generates studio shots, lifestyle scenes, color
            and angle variants, and a short product video — each carrying a verifiable provenance
            manifest, so buyers can tell what&apos;s authentic from what&apos;s AI.
          </p>

          <div className="mt-8 flex flex-col gap-3 sm:flex-row">
            <Link
              href="/studio"
              className={`${buttonVariants({ variant: "accent", size: "lg" })} w-full sm:w-auto`}
            >
              <Wand2 /> Generate your first pack
            </Link>
            <Link
              href="/how-it-works"
              className={`${buttonVariants({ variant: "outline", size: "lg" })} w-full sm:w-auto`}
            >
              See how it works <ArrowRight />
            </Link>
          </div>

          <dl className="mt-10 grid max-w-md grid-cols-3 gap-4 border-t pt-6">
            {FIGURES.map((f) => (
              <div key={f.label}>
                <dt className="tabular text-2xl font-semibold tracking-tight">{f.value}</dt>
                <dd className="mt-0.5 text-xs text-muted-foreground">{f.label}</dd>
              </div>
            ))}
          </dl>
        </FadeIn>

        <FadeIn delay={0.12} y={16}>
          <PackShowcase />
        </FadeIn>
      </div>
    </section>
  );
}
