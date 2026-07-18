import { Boxes, Camera, Film, ImageIcon, Palette, UserRound } from "lucide-react";
import type { LucideIcon } from "lucide-react";

import { cn } from "@/lib/utils";

/**
 * The real pipeline.
 *
 * Model IDs here are the ones in `backend/originshot_pipelines/registry.py` —
 * not representative stand-ins. Four image styles share a single model, which is
 * the actual shape of the system and worth showing plainly: one model, read
 * once, fanned out into four framings. Keep this in step with the registry.
 */

interface Output {
  label: string;
  icon: LucideIcon;
  count: number;
}

const IMAGE_OUTPUTS: Output[] = [
  { label: "Studio", icon: ImageIcon, count: 1 },
  { label: "Lifestyle", icon: Boxes, count: 2 },
  { label: "On model", icon: UserRound, count: 1 },
  { label: "Variants", icon: Palette, count: 2 },
];

function Stage({
  eyebrow,
  model,
  children,
  className,
}: {
  eyebrow: string;
  model: string;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <div className={cn("flex min-w-0 flex-col rounded-lg border bg-card p-5", className)}>
      <p className="label text-muted-foreground">{eyebrow}</p>
      <p className="mt-1.5 truncate font-mono text-xs text-accent" title={model}>
        {model}
      </p>
      <div className="mt-4">{children}</div>
    </div>
  );
}

export function PipelineFlow({ className }: { className?: string }) {
  return (
    <div className={cn("grid gap-4 lg:grid-cols-[minmax(0,0.6fr)_minmax(0,1.4fr)_minmax(0,0.7fr)]", className)}>
      {/* Source */}
      <div className="flex min-w-0 flex-col rounded-lg border bg-muted/40 p-5">
        <p className="label text-muted-foreground">Source</p>
        <p className="mt-1.5 font-mono text-xs text-verified">your photo</p>
        <div className="mt-4 flex items-center gap-2.5">
          <span className="grid size-9 shrink-0 place-items-center rounded-md border bg-card text-verified">
            <Camera className="size-4" />
          </span>
          <span className="min-w-0 text-sm">
            <span className="font-medium">Original</span>
            <span className="block text-xs text-muted-foreground">hashed, EXIF stripped</span>
          </span>
        </div>
      </div>

      {/* One image model, four framings */}
      <Stage eyebrow="Image styles" model="gemini-3-pro-image-preview">
        <ul className="grid grid-cols-2 gap-2.5">
          {IMAGE_OUTPUTS.map(({ label, icon: Icon, count }) => (
            <li key={label} className="flex items-center gap-2 rounded-md border bg-background p-2">
              <Icon className="size-4 shrink-0 text-muted-foreground" />
              <span className="min-w-0 truncate text-[13px] font-medium">{label}</span>
              <span className="tabular ms-auto shrink-0 font-mono text-[11px] text-muted-foreground">
                ×{count}
              </span>
            </li>
          ))}
        </ul>
      </Stage>

      {/* Video is the one step with a real fallback chain */}
      <Stage eyebrow="Video" model="Kling-Image2Video-V2.1-Master">
        <div className="flex items-center gap-2.5 rounded-md border bg-background p-2">
          <Film className="size-4 shrink-0 text-muted-foreground" />
          <span className="min-w-0 truncate text-[13px] font-medium">Product clip</span>
          <span className="tabular ms-auto shrink-0 font-mono text-[11px] text-muted-foreground">
            ×1
          </span>
        </div>
        <p className="mt-3 text-xs text-muted-foreground">
          Falls back to{" "}
          <span className="font-mono text-[11px]">pixverse-v5.6-i2v</span> then{" "}
          <span className="font-mono text-[11px]">wan2.6-r2v</span> if the primary is slow or
          fails.
        </p>
      </Stage>
    </div>
  );
}
