import { ClosingCta } from "@/components/landing/closing-cta";
import { Evidence } from "@/components/landing/evidence";
import { LandingFooter } from "@/components/landing/landing-footer";
import { LandingHeader } from "@/components/landing/landing-header";
import { LandingHero } from "@/components/landing/hero";
import { PackGallery } from "@/components/landing/pack-gallery";
import { RunSequence } from "@/components/landing/run-sequence";
import { Stack } from "@/components/landing/stack";

/**
 * The landing page runs as an argument, not a stack of feature blocks:
 *
 *   here is a real pack arriving (hero) → they all came from one photo
 *   (gallery) → this is how (run) → here is why you can believe it (evidence)
 *   → and here is what it stands on (stack).
 *
 * The art direction is the "Light Table" band system in globals.css, which is
 * global rather than scoped to this page — the same bands carry /how-it-works
 * and /about, so the public surface reads as one room.
 */
export default function Home() {
  return (
    <div className="band-ink min-h-dvh">
      <LandingHeader />
      <main>
        <LandingHero />
        <PackGallery />
        <RunSequence />
        <Evidence />
        <Stack />
        <ClosingCta />
      </main>
      <LandingFooter />
    </div>
  );
}
