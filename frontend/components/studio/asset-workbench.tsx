"use client";

import { useMemo } from "react";

import type { Asset, Style } from "@/lib/types";
import { ImageTile } from "@/components/image-tile";
import { Stagger, StaggerItem } from "@/components/motion/stagger";
import { MediaSkeleton } from "@/components/ui/skeleton";

/**
 * The generated pack, grouped the way a seller works through it rather than as
 * one flat wall of thumbnails. Each group states how many frames it holds, so
 * "did the on-model step actually run?" is answerable at a glance — which is
 * the question people actually have while a job is finishing.
 */
const GROUP_ORDER: { style: Style; label: string; blurb: string }[] = [
  { style: "studio", label: "Studio", blurb: "White background, marketplace main image" },
  { style: "lifestyle", label: "Lifestyle", blurb: "In-context scenes for the listing gallery" },
  { style: "onmodel", label: "On model", blurb: "Scale and fit" },
  { style: "variant", label: "Variants", blurb: "Colour and angle sweeps" },
  { style: "video", label: "Video", blurb: "Short product clip" },
];

export function AssetWorkbench({
  assets,
  pendingStyles = [],
  onSelect,
}: {
  assets: Asset[];
  /** Styles with a step still running — renders developing placeholders. */
  pendingStyles?: Style[];
  onSelect: (a: Asset) => void;
}) {
  const groups = useMemo(() => {
    return GROUP_ORDER.map((g) => ({
      ...g,
      items: assets.filter((a) => a.style === g.style),
      pending: pendingStyles.includes(g.style),
    })).filter((g) => g.items.length > 0 || g.pending);
  }, [assets, pendingStyles]);

  if (groups.length === 0) return null;

  return (
    <div className="space-y-10">
      {groups.map((g) => (
        <section key={g.style}>
          <div className="mb-4 flex items-baseline justify-between gap-3 border-b pb-2">
            <div className="flex items-baseline gap-3">
              <h3 className="label text-foreground">{g.label}</h3>
              <p className="truncate text-xs text-muted-foreground max-sm:hidden">{g.blurb}</p>
            </div>
            <span className="tabular shrink-0 font-mono text-xs text-muted-foreground">
              {g.pending && g.items.length === 0
                ? "running"
                : `${g.items.length} frame${g.items.length === 1 ? "" : "s"}`}
            </span>
          </div>

          <Stagger className="grid grid-cols-2 gap-4 sm:grid-cols-3 xl:grid-cols-4">
            {g.items.map((a) => (
              <StaggerItem key={a.id}>
                <ImageTile asset={a} onClick={() => onSelect(a)} />
              </StaggerItem>
            ))}
            {/* A slot for the frame that hasn't landed yet, so the grid doesn't
                jump when it does. */}
            {g.pending && (
              <MediaSkeleton
                aspect={
                  g.style === "video"
                    ? "aspect-video"
                    : g.style === "lifestyle" || g.style === "onmodel"
                      ? "aspect-[4/5]"
                      : "aspect-square"
                }
              />
            )}
          </Stagger>
        </section>
      ))}
    </div>
  );
}
