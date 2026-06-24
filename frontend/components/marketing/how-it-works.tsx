import { Camera, ShieldCheck, Wand2 } from "lucide-react";

import { MarketingSection } from "./section";
import { StepFlow, type FlowStep } from "./step-flow";

const STEPS: FlowStep[] = [
  {
    icon: Camera,
    title: "Upload one photo",
    body: "Drop a single phone photo of your product. We validate it, strip EXIF/GPS, and anchor it as the authentic original.",
  },
  {
    icon: Wand2,
    title: "Generate the pack",
    body: "Pick styles and target marketplaces. ListSnap runs multi-step pipelines to produce studio, lifestyle, variant, and video outputs.",
  },
  {
    icon: ShieldCheck,
    title: "Verify & publish",
    body: "Every output carries an embedded provenance manifest. Anyone can re-check authenticity from the file itself — no trust required.",
  },
];

export function HowItWorks() {
  return (
    <MarketingSection
      eyebrow="How it works"
      title="From a single snapshot to a marketplace-ready pack"
      description="Three steps. No studio, no shoot, no guesswork about what's real."
      className="border-b"
    >
      <StepFlow steps={STEPS} />
    </MarketingSection>
  );
}
