import type { ReactNode } from "react";

import { cn } from "@/lib/utils";
import { RegistrationStrip, type RegistrationState } from "./registration";

/**
 * A region of a screen — the app's unit of layout.
 *
 * This replaces the Card-stack rhythm the dashboard used to be built from.
 * A page made of bordered cards on a tinted ground reads as a stack of
 * unrelated widgets: every panel claims the same weight, and the eye gets no
 * hierarchy for free. A Section instead divides with a rule and names itself
 * with a micro-label, which is how a spec sheet or a contact sheet is
 * organised — continuous surface, hairline divisions, the content doing the
 * talking.
 *
 * Card is still correct, but only for genuinely detachable objects: a media
 * tile, a SKU, something you could pick up and move somewhere else. If it
 * can't be picked up, it's a Section.
 */
export function Section({
  label,
  description,
  action,
  state,
  framed = false,
  children,
  className,
}: {
  /** Micro-label naming the region. Kept short — it's a legend, not a heading. */
  label?: string;
  description?: string;
  action?: ReactNode;
  /** Surfaces live state on the region's leading edge. Omit for static regions. */
  state?: RegistrationState;
  /** Opt into a bordered surface for content that genuinely needs containment. */
  framed?: boolean;
  children: ReactNode;
  className?: string;
}) {
  const header = label || action || description;

  return (
    <section className={cn("min-w-0", className)}>
      {header && (
        <div
          className={cn(
            "flex flex-wrap items-end justify-between gap-x-4 gap-y-2 pb-3",
            // The rule is the division. Framed sections get their border from
            // the surface instead, so a doubled line never appears.
            !framed && "border-b",
          )}
        >
          <div className="flex min-w-0 items-center gap-2.5">
            {state && <RegistrationStrip state={state} className="h-4" />}
            <div className="min-w-0">
              {label && <h2 className="label text-muted-foreground">{label}</h2>}
              {description && (
                <p className="mt-1 text-sm text-muted-foreground">{description}</p>
              )}
            </div>
          </div>
          {action && <div className="shrink-0">{action}</div>}
        </div>
      )}

      <div
        className={cn(
          header && !framed && "pt-4",
          framed && "rounded-lg border bg-card shadow-raised",
          framed && header && "mt-3",
        )}
      >
        {children}
      </div>
    </section>
  );
}

/**
 * A numbered stage in a real sequence.
 *
 * Numbering is only honest when order is information the reader needs. Catalog
 * Mode qualifies — you cannot choose output formats before there are photos to
 * apply them to, and you cannot run before both. Do NOT reach for this to
 * decorate a set of peer regions; those are Sections.
 *
 * A completed step trades its number for a check, so the marker column reads as
 * progress at a glance rather than as ornament.
 */
export function Step({
  n,
  label,
  description,
  done = false,
  children,
  className,
}: {
  n: number;
  label: string;
  description?: string;
  done?: boolean;
  children: ReactNode;
  className?: string;
}) {
  return (
    <section className={cn("min-w-0", className)}>
      <div className="flex items-center gap-3 border-b pb-3">
        <span
          aria-hidden
          className={cn(
            "tabular grid size-6 shrink-0 place-items-center rounded-full font-mono text-[11px] font-medium",
            done
              ? "bg-verified-surface text-verified"
              : "border text-muted-foreground",
          )}
        >
          {done ? "✓" : n}
        </span>
        <div className="min-w-0">
          <h2 className="label text-muted-foreground">
            {/* The number is decorative in the marker; screen readers get it here. */}
            <span className="sr-only">Step {n}: </span>
            {label}
          </h2>
          {description && <p className="mt-1 text-sm text-muted-foreground">{description}</p>}
        </div>
      </div>
      <div className="pt-4">{children}</div>
    </section>
  );
}

/**
 * The hairline lattice.
 *
 * Cells are separated by the grid's own background showing through a 1px gap,
 * so N tiles share N-1 rules instead of drawing 4N borders that double up at
 * every seam. This is the pattern StatGrid already used for metrics; it is the
 * right answer for any set of peer cells, so it lives here now and StatGrid is
 * one caller of it.
 */
export function Lattice({
  columns = 4,
  children,
  className,
}: {
  columns?: 2 | 3 | 4;
  children: ReactNode;
  className?: string;
}) {
  return (
    <div
      className={cn(
        "grid gap-px overflow-hidden rounded-lg border bg-border",
        columns === 2 && "sm:grid-cols-2",
        columns === 3 && "sm:grid-cols-2 lg:grid-cols-3",
        columns === 4 && "sm:grid-cols-2 lg:grid-cols-4",
        className,
      )}
    >
      {children}
    </div>
  );
}

/**
 * Vertical rhythm for a screen. One knob, so pages can't drift apart on
 * spacing the way eight independently written `space-y-*` stacks did.
 */
export function Stack({
  gap = "normal",
  children,
  className,
}: {
  gap?: "tight" | "normal" | "loose";
  children: ReactNode;
  className?: string;
}) {
  return (
    <div
      className={cn(
        gap === "tight" && "space-y-6",
        gap === "normal" && "space-y-10",
        gap === "loose" && "space-y-14",
        className,
      )}
    >
      {children}
    </div>
  );
}
