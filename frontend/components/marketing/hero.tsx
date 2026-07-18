import Link from "next/link";
import { ArrowRight } from "lucide-react";

import { buttonVariants } from "@/components/ui/button";
import { FadeIn } from "@/components/motion/fade-in";
import { ContactSheet } from "./contact-sheet";

/**
 * The hero leads with the proof rather than a promise: the contact sheet is a
 * real run, so the page's first impression is the product's actual output.
 */
export function Hero() {
  return (
    <section className="relative overflow-hidden border-b">
      <div aria-hidden className="patch-grid patch-grid-fade absolute inset-0 -z-10" />

      <div className="mx-auto max-w-[1400px] px-4 py-14 sm:px-6 sm:py-20 lg:px-8">
        <div className="grid items-center gap-10 lg:grid-cols-[minmax(0,0.85fr)_minmax(0,1fr)] lg:gap-14">
          <FadeIn className="min-w-0">
            <p className="label text-muted-foreground">Product photography, calibrated</p>

            <h1 className="display mt-4 text-[2.5rem] sm:text-6xl lg:text-[4.25rem]">
              One photo in.
              <br />
              <span className="text-muted-foreground">A whole catalog out.</span>
            </h1>

            <p className="mt-6 max-w-xl text-pretty text-base text-muted-foreground sm:text-lg">
              Photograph your product once, on your phone. OriginShot returns studio shots,
              lifestyle scenes, colour and angle variants, and a short product video — each one
              carrying a provenance manifest a buyer can check.
            </p>

            <div className="mt-8 flex flex-col gap-3 sm:flex-row">
              <Link
                href="/studio"
                className={`${buttonVariants({ variant: "accent", size: "lg" })} w-full sm:w-auto`}
              >
                Generate your first pack
              </Link>
              <Link
                href="/how-it-works"
                className={`${buttonVariants({ variant: "outline", size: "lg" })} w-full sm:w-auto`}
              >
                See how it works <ArrowRight />
              </Link>
            </div>

            {/* Numbers are taken from backend/app/pricing.py — a full pack is
                studio 1 + lifestyle 2 + on-model 1 + variants 2 + video 1. Keep
                them in step with _OUTPUTS if the pipeline changes. */}
            <dl className="mt-10 grid max-w-lg grid-cols-3 gap-6 border-t pt-6">
              {[
                { v: "7", l: "assets per pack" },
                { v: "5", l: "marketplace presets" },
                { v: "100%", l: "hash-verifiable" },
              ].map((f) => (
                <div key={f.l} className="min-w-0">
                  <dt className="tabular text-2xl font-semibold tracking-tight sm:text-3xl">
                    {f.v}
                  </dt>
                  <dd className="mt-1 text-xs text-muted-foreground">{f.l}</dd>
                </div>
              ))}
            </dl>
          </FadeIn>

          <FadeIn delay={0.1} y={16} className="min-w-0">
            <ContactSheet />
          </FadeIn>
        </div>
      </div>
    </section>
  );
}
