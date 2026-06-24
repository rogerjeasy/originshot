import {
  Boxes,
  Database,
  Film,
  Image as ImageIcon,
  Palette,
  ShieldCheck,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Stagger, StaggerItem } from "@/components/motion/stagger";
import { MarketingSection } from "./section";

interface Feature {
  icon: LucideIcon;
  title: string;
  body: string;
}

const FEATURES: Feature[] = [
  {
    icon: ImageIcon,
    title: "Studio shots",
    body: "Clean, pure-white-background product photography generated from your single source image.",
  },
  {
    icon: Boxes,
    title: "Lifestyle & on-model",
    body: "Place the product in realistic scenes and on models to show context and scale.",
  },
  {
    icon: Palette,
    title: "Color & angle variants",
    body: "Sweep colorways and viewpoints to fill out a catalog without another shoot.",
  },
  {
    icon: Film,
    title: "Product video",
    body: "A short hero clip rendered from the studio image — motion that converts on listings.",
  },
  {
    icon: ShieldCheck,
    title: "Embedded provenance",
    body: "Each asset carries a signed manifest. Re-verify authenticity straight from the file's bytes.",
  },
  {
    icon: Database,
    title: "Backblaze B2 storage",
    body: "Content-addressable storage means identical bytes are stored once — provenance and dedup, built in.",
  },
];

export function FeatureGrid() {
  return (
    <MarketingSection
      eyebrow="Everything in one pack"
      title="A full catalog from one input"
      description="The generated media is the star — framed like a gallery, verifiable like a certificate."
      className="border-b"
    >
      <Stagger className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {FEATURES.map(({ icon: Icon, title, body }) => (
          <StaggerItem key={title} className="h-full">
            <Card className="lift h-full">
              <CardHeader>
                <span className="mb-1 inline-grid size-10 place-items-center rounded-xl bg-secondary text-secondary-foreground ring-1 ring-border">
                  <Icon className="size-5" />
                </span>
                <CardTitle className="text-base">{title}</CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-sm text-muted-foreground">{body}</p>
              </CardContent>
            </Card>
          </StaggerItem>
        ))}
      </Stagger>
    </MarketingSection>
  );
}
