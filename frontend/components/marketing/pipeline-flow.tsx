import { Fragment } from "react";
import { ArrowRight, Boxes, Camera, Film, ImageIcon, Palette } from "lucide-react";
import type { LucideIcon } from "lucide-react";

import { cn } from "@/lib/utils";

interface Stage {
  label: string;
  model: string;
  icon: LucideIcon;
  authentic?: boolean;
}

/** The Genblaze multi-step pipeline, image → variants → video, with provider/model in mono. */
const STAGES: Stage[] = [
  { label: "Original", model: "your photo", icon: Camera, authentic: true },
  { label: "Studio", model: "seedream-3", icon: ImageIcon },
  { label: "Lifestyle", model: "flux-1", icon: Boxes },
  { label: "Variants", model: "gemini-img", icon: Palette },
  { label: "Video", model: "kling-1.6", icon: Film },
];

function StageCard({ stage }: { stage: Stage }) {
  const Icon = stage.icon;
  return (
    <div className="lift flex flex-1 flex-col items-center gap-2 rounded-2xl border bg-card p-5 text-center">
      <span
        className={cn(
          "grid size-11 place-items-center rounded-xl ring-1 ring-border",
          stage.authentic ? "bg-verified/10 text-verified" : "bg-secondary text-foreground",
        )}
      >
        <Icon className="size-5" />
      </span>
      <p className="text-sm font-semibold tracking-tight">{stage.label}</p>
      <p className="font-mono text-[11px] text-muted-foreground">{stage.model}</p>
    </div>
  );
}

export function PipelineFlow({ className }: { className?: string }) {
  return (
    <div
      className={cn(
        "flex flex-col items-stretch gap-3 lg:flex-row lg:items-center",
        className,
      )}
    >
      {STAGES.map((stage, i) => (
        <Fragment key={stage.label}>
          <StageCard stage={stage} />
          {i < STAGES.length - 1 && (
            <ArrowRight
              aria-hidden
              className="mx-auto size-5 shrink-0 rotate-90 text-muted-foreground lg:rotate-0"
            />
          )}
        </Fragment>
      ))}
    </div>
  );
}
