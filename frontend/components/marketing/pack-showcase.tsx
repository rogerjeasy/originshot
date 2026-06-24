"use client";

import type { LucideIcon } from "lucide-react";
import { Boxes, Film, ImageIcon, Palette, Play } from "lucide-react";

import { cn } from "@/lib/utils";
import { ProvenanceBadge } from "@/components/provenance-badge";
import { Stagger, StaggerItem } from "@/components/motion/stagger";

interface Plate {
  label: string;
  icon: LucideIcon;
  aspect: string;
  authentic?: boolean;
  sha: string;
  video?: boolean;
}

/**
 * The hero centerpiece: a framed studio "wall" of the generated pack. Every tile
 * is a gallery-framed object carrying a provenance pill — the product's image-first,
 * trust-by-design story rendered without needing real raster assets.
 */
const PLATES: Plate[] = [
  {
    label: "Original",
    icon: ImageIcon,
    aspect: "aspect-square",
    authentic: true,
    sha: "7f3a9c2e1b4d5a6f8c0e2d4b6a8c0e1f",
  },
  { label: "Studio", icon: ImageIcon, aspect: "aspect-square", sha: "a1b2c3d4e5f60718293a4b5c6d7e8f90" },
  { label: "Lifestyle", icon: Boxes, aspect: "aspect-[4/5]", sha: "b2c3d4e5f6a7081928374655a4b3c2d1" },
  { label: "Variant", icon: Palette, aspect: "aspect-square", sha: "c3d4e5f6a7b80192837465540312a9f8" },
  {
    label: "Product video",
    icon: Film,
    aspect: "aspect-video",
    sha: "d4e5f6a7b8c90123456789abcdef0123",
    video: true,
  },
];

function Plate({ plate }: { plate: Plate }) {
  const Icon = plate.icon;
  return (
    <div
      className={cn(
        "group relative w-full overflow-hidden rounded-xl border bg-card studio-sweep frame",
        plate.aspect,
      )}
    >
      {/* faint studio backdrop highlight */}
      <div className="plate-sweep pointer-events-none absolute inset-0" />
      {/* large watermark glyph stands in for the framed media */}
      <Icon
        className={cn(
          "absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 size-10 text-muted-foreground/40 transition-transform duration-300 group-hover:scale-110",
          plate.authentic && "text-verified/40",
        )}
        strokeWidth={1.25}
      />
      {plate.video && (
        <span className="absolute left-1/2 top-1/2 grid size-9 -translate-x-1/2 -translate-y-1/2 place-items-center rounded-full border bg-background/80 backdrop-blur">
          <Play className="size-4 fill-current" />
        </span>
      )}
      <div className="absolute inset-x-2 bottom-2 flex items-center justify-between gap-2">
        <span className="rounded-md bg-background/75 px-1.5 py-0.5 text-[11px] font-medium backdrop-blur">
          {plate.label}
        </span>
        <ProvenanceBadge
          authentic={Boolean(plate.authentic)}
          sha={plate.sha}
          className="bg-background/75 backdrop-blur [&>span:nth-child(2)]:hidden sm:[&>span:nth-child(2)]:inline"
        />
      </div>
    </div>
  );
}

export function PackShowcase({ className }: { className?: string }) {
  return (
    <div className={cn("relative", className)}>
      {/* ambient glow behind the well */}
      <div className="glow-cobalt pointer-events-none absolute -inset-6 -z-10 blur-2xl" />
      <div className="frame-deep rounded-2xl border bg-card/60 p-3 backdrop-blur-sm sm:p-4">
        {/* studio caption bar */}
        <div className="mb-3 flex items-center justify-between gap-2 px-1">
          <div className="flex items-center gap-1.5">
            <span className="size-2.5 rounded-full bg-danger/70" />
            <span className="size-2.5 rounded-full bg-warning/70" />
            <span className="size-2.5 rounded-full bg-verified/70" />
          </div>
          <span className="font-mono text-[11px] text-muted-foreground">
            studio-pack · 12 assets · all verified
          </span>
        </div>

        <Stagger className="grid grid-cols-2 items-start gap-3">
          <StaggerItem>
            <Plate plate={PLATES[0]} />
          </StaggerItem>
          <StaggerItem>
            <Plate plate={PLATES[1]} />
          </StaggerItem>
          <StaggerItem className="col-span-1">
            <Plate plate={PLATES[2]} />
          </StaggerItem>
          <StaggerItem className="flex flex-col gap-3">
            <Plate plate={PLATES[3]} />
            <Plate plate={PLATES[4]} />
          </StaggerItem>
        </Stagger>
      </div>
    </div>
  );
}
