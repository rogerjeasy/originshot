"use client";

import { cn } from "@/lib/utils";
import type { Asset } from "@/lib/types";
import { ProvenanceBadge } from "./provenance-badge";

const ASPECT: Record<string, string> = {
  studio: "aspect-square",
  variant: "aspect-square",
  original: "aspect-square",
  lifestyle: "aspect-[4/5]",
  onmodel: "aspect-[4/5]",
  video: "aspect-video",
};

export function ImageTile({ asset, onClick }: { asset: Asset; onClick?: () => void }) {
  const ar = ASPECT[asset.style] ?? "aspect-square";
  return (
    <button type="button" onClick={onClick} className="group block w-full min-w-0 text-start">
      <div className={cn("frame lift relative overflow-hidden rounded-xl border bg-muted", ar)}>
        {asset.modality === "video" ? (
          // eslint-disable-next-line jsx-a11y/media-has-caption
          <video src={asset.url ?? undefined} className="size-full object-cover" muted playsInline />
        ) : (
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={asset.url ?? undefined}
            alt={`${asset.style} product image`}
            className="size-full object-cover transition-transform duration-200 group-hover:scale-[1.02]"
            loading="lazy"
          />
        )}
        <div className="absolute bottom-2 start-2">
          <ProvenanceBadge authentic={asset.is_authentic} sha={asset.sha256} />
        </div>
      </div>
      <div className="mt-2 flex items-center justify-between gap-2">
        <span className="truncate text-sm font-medium capitalize">{asset.style}</span>
        <span className="shrink-0 font-mono text-xs text-muted-foreground">
          {asset.width && asset.height ? `${asset.width}×${asset.height}` : asset.modality}
        </span>
      </div>
    </button>
  );
}
