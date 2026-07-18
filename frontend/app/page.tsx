import { CtaBand } from "@/components/marketing/cta-band";
import { FeatureGrid } from "@/components/marketing/feature-grid";
import { Hero } from "@/components/marketing/hero";
import { HowItWorks } from "@/components/marketing/how-it-works";
import { MarketingHeader } from "@/components/marketing/marketing-header";
import { ProvenanceSpotlight } from "@/components/marketing/provenance-spotlight";
import { TrustStrip } from "@/components/marketing/trust-strip";
import { WhyOriginShot } from "@/components/marketing/why-originshot";
import { FadeIn } from "@/components/motion/fade-in";
import { SiteFooter } from "@/components/site-footer";

export default function Home() {
  return (
    <div className="min-h-dvh">
      <MarketingHeader />
      <main>
        <Hero />
        <section className="border-b py-12">
          <FadeIn className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
            <TrustStrip />
          </FadeIn>
        </section>
        <HowItWorks />
        <FeatureGrid />
        <ProvenanceSpotlight />
        <WhyOriginShot />
        <CtaBand />
      </main>
      <SiteFooter />
    </div>
  );
}
