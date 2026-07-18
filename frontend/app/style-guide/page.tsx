import type { Metadata } from "next";

import { PublicHeader } from "@/components/public-header";
import { SiteFooter } from "@/components/site-footer";
import { BadgeGallery } from "@/components/style-guide/badge-gallery";
import { ButtonGallery } from "@/components/style-guide/button-gallery";
import { ColorSwatches } from "@/components/style-guide/color-swatches";
import { PatternShowcase } from "@/components/style-guide/pattern-showcase";
import { SgSection } from "@/components/style-guide/sg-section";
import { TypeScale } from "@/components/style-guide/type-scale";

export const metadata: Metadata = {
  title: "Design system — OriginShot",
  description: "OriginShot design tokens and components reference.",
};

export default function StyleGuidePage() {
  return (
    <div className="min-h-dvh">
      <PublicHeader />
      <main className="mx-auto max-w-7xl space-y-12 px-4 py-12 sm:px-6 lg:px-8">
        <header>
          <h1 className="text-2xl font-semibold tracking-tight">Design system</h1>
          <p className="text-muted-foreground">
            Tokens &amp; components — the shared language behind every screen. See{" "}
            <span className="font-mono">docs/DESIGN_SYSTEM.md</span>.
          </p>
        </header>

        <SgSection title="Color">
          <ColorSwatches />
        </SgSection>

        <SgSection title="Typography">
          <TypeScale />
        </SgSection>

        <SgSection title="Buttons">
          <ButtonGallery />
        </SgSection>

        <SgSection title="Badges & provenance">
          <BadgeGallery />
        </SgSection>

        <SgSection title="Patterns">
          <PatternShowcase />
        </SgSection>
      </main>
      <SiteFooter />
    </div>
  );
}
