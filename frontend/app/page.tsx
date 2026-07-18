import { CtaBand } from "@/components/marketing/cta-band";
import { Hero } from "@/components/marketing/hero";
import { MarketingHeader } from "@/components/marketing/marketing-header";
import { PackShowcase } from "@/components/marketing/pack-showcase";
import { Pipeline } from "@/components/marketing/pipeline";
import { ProvenanceSpotlight } from "@/components/marketing/provenance-spotlight";
import { SiteFooter } from "@/components/site-footer";

/**
 * The landing page runs as an argument rather than a stack of feature blocks:
 * here is the real output (hero) → they all came from one photo (showcase) →
 * this is how (pipeline) → and here is why you can believe it (provenance).
 */
export default function Home() {
  return (
    <div className="min-h-dvh">
      <MarketingHeader />
      <main>
        <Hero />
        <PackShowcase />
        <Pipeline />
        <ProvenanceSpotlight />
        <CtaBand />
      </main>
      <SiteFooter />
    </div>
  );
}
