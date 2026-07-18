import Link from "next/link";
import { ShieldCheck } from "lucide-react";

import { buttonVariants } from "@/components/ui/button";

/** Closing call to action, set on the calibration grid. */
export function CtaBand() {
  return (
    <section className="relative overflow-hidden border-t">
      <div aria-hidden className="patch-grid patch-grid-fade absolute inset-0 -z-10" />
      <div className="mx-auto max-w-3xl px-4 py-20 text-center sm:px-6 sm:py-28 lg:px-8">
        <h2 className="text-balance text-3xl font-semibold tracking-[-0.03em] sm:text-4xl">
          Your next listing photo is already good enough
        </h2>
        <p className="mx-auto mt-4 max-w-xl text-pretty text-muted-foreground sm:text-lg">
          Upload one shot and get the pack back in a couple of minutes — stored on Backblaze B2,
          with provenance a buyer can check.
        </p>
        <div className="mt-9 flex flex-col items-center justify-center gap-3 sm:flex-row">
          <Link
            href="/studio"
            className={`${buttonVariants({ variant: "accent", size: "lg" })} w-full sm:w-auto`}
          >
            Open the Studio
          </Link>
          <Link
            href="/verify"
            className={`${buttonVariants({ variant: "outline", size: "lg" })} w-full sm:w-auto`}
          >
            <ShieldCheck /> Verify a file
          </Link>
        </div>
      </div>
    </section>
  );
}
