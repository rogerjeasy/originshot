"use client";

import { Maximize2, Play } from "lucide-react";

import { cn } from "@/lib/utils";
import type { Asset } from "@/lib/types";
import { ProvenanceBadge } from "./provenance-badge";

/** Locked per style so a grid never reflows as assets land one by one. */
const ASPECT: Record<string, string> = {
  studio: "aspect-square",
  variant: "aspect-square",
  original: "aspect-square",
  lifestyle: "aspect-[4/5]",
  onmodel: "aspect-[4/5]",
  video: "aspect-video",
};

const STYLE_LABEL: Record<string, string> = {
  original: "Original",
  studio: "Studio",
  lifestyle: "Lifestyle",
  onmodel: "On model",
  variant: "Variant",
  video: "Video",
};

/**
 * A generated asset as a mounted print: framed media plate above, caption strip
 * below. The caption is the contact-sheet legend — style in sans, machine facts
 * in mono — so the two kinds of information never blur together.
 */
export function ImageTile({
  asset,
  onClick,
  className,
}: {
  asset: Asset;
  onClick?: () => void;
  className?: string;
}) {
  const ar = ASPECT[asset.style] ?? "aspect-square";
  const dims = asset.width && asset.height ? `${asset.width}×${asset.height}` : null;
  const label = STYLE_LABEL[asset.style] ?? asset.style;

  return (
    <button
      type="button"
      onClick={onClick}
      className={cn("group block w-full min-w-0 text-start", className)}
      aria-label={`${label} asset — open preview`}
    >
      <div className={cn("frame lift relative overflow-hidden rounded-md border bg-muted", ar)}>
        {asset.modality === "video" ? (
          <>
            {/* eslint-disable-next-line jsx-a11y/media-has-caption */}
            <video
              src={asset.url ?? undefined}
              className="size-full object-cover"
              muted
              playsInline
              preload="metadata"
            />
            <span className="pointer-events-none absolute inset-0 grid place-items-center">
              <span className="grid size-11 place-items-center rounded-full bg-black/55 text-white backdrop-blur-sm">
                <Play className="size-4 fill-current" />
              </span>
            </span>
          </>
        ) : (
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={asset.url ?? undefined}
            alt={`${label} product shot`}
            className="size-full object-cover transition-transform duration-300 ease-out group-hover:scale-[1.03]"
            loading="lazy"
          />
        )}

        {/* Provenance sits on the plate itself — the claim travels with the image. */}
        <span className="absolute inset-x-2 bottom-2 flex justify-start">
          <ProvenanceBadge
            authentic={asset.is_authentic}
            sha={asset.sha256}
            compact
            className="bg-card/85 backdrop-blur-sm"
          />
        </span>

        {/* Zoom affordance appears on intent, not permanently. */}
        <span className="absolute end-2 top-2 grid size-7 place-items-center rounded-md bg-card/85 text-muted-foreground opacity-0 backdrop-blur-sm transition-opacity duration-150 group-hover:opacity-100 group-focus-visible:opacity-100">
          <Maximize2 className="size-3.5" />
        </span>
      </div>

      <div className="mt-2 flex items-baseline justify-between gap-2">
        <span className="truncate text-[13px] font-medium">{label}</span>
        <span className="tabular shrink-0 font-mono text-[11px] text-muted-foreground">
          {dims ?? asset.modality}
        </span>
      </div>
    </button>
  );
}
