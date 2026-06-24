import Link from "next/link";
import { ShieldCheck, Wand2 } from "lucide-react";

import { FadeIn } from "@/components/motion/fade-in";
import { buttonVariants } from "@/components/ui/button";

/** Closing call-to-action band on the seamless sweep with a soft cobalt signal. */
export function CtaBand() {
  return (
    <section className="relative overflow-hidden border-b">
      <div aria-hidden className="bg-grid absolute inset-0 -z-10" />
      <div aria-hidden className="glow-cobalt absolute inset-x-0 bottom-0 -z-10 h-[360px]" />
      <FadeIn className="mx-auto max-w-3xl px-4 py-20 text-center sm:px-6 sm:py-24 lg:px-8">
        <h2 className="text-balance text-3xl font-semibold tracking-tight sm:text-4xl">
          Turn your next photo into a full pack
        </h2>
        <p className="mx-auto mt-3 max-w-xl text-pretty text-muted-foreground">
          No studio, no shoot. Upload one image and publish a verified, marketplace-ready catalog —
          stored durably on Backblaze B2.
        </p>
        <div className="mt-8 flex flex-col items-center justify-center gap-3 sm:flex-row">
          <Link
            href="/studio"
            className={`${buttonVariants({ variant: "accent", size: "lg" })} w-full sm:w-auto`}
          >
            <Wand2 /> Open the Studio
          </Link>
          <Link
            href="/verify"
            className={`${buttonVariants({ variant: "outline", size: "lg" })} w-full sm:w-auto`}
          >
            <ShieldCheck /> Verify a file
          </Link>
        </div>
      </FadeIn>
    </section>
  );
}
