import type { LucideIcon } from "lucide-react";

import { cn } from "@/lib/utils";
import { Stagger, StaggerItem } from "@/components/motion/stagger";

export interface FlowStep {
  icon: LucideIcon;
  title: string;
  body: string;
}

/**
 * Numbered step cards with a connecting rail on large screens + staggered reveal.
 * Renders icons here (server-safe) and only passes rendered children into the
 * client <Stagger>, so no component functions cross the server/client boundary.
 */
export function StepFlow({ steps, className }: { steps: FlowStep[]; className?: string }) {
  return (
    <div className={cn("relative", className)}>
      <div
        aria-hidden
        className="absolute inset-x-[12%] top-11 hidden h-px bg-gradient-to-r from-transparent via-border to-transparent md:block"
      />
      <Stagger className="grid gap-6 md:grid-cols-3">
        {steps.map(({ icon: Icon, title, body }, i) => (
          <StaggerItem key={title}>
            <div className="lift relative h-full rounded-2xl border bg-card p-6">
              <div className="mb-4 flex items-center justify-between">
                <span className="inline-grid size-11 place-items-center rounded-xl bg-secondary text-foreground ring-1 ring-border">
                  <Icon className="size-5" />
                </span>
                <span className="font-mono text-sm text-muted-foreground">0{i + 1}</span>
              </div>
              <h3 className="font-semibold tracking-tight">{title}</h3>
              <p className="mt-2 text-sm text-muted-foreground">{body}</p>
            </div>
          </StaggerItem>
        ))}
      </Stagger>
    </div>
  );
}
