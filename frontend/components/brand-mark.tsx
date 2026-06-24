import Link from "next/link";
import { Aperture } from "lucide-react";

import { cn } from "@/lib/utils";

/**
 * The ListSnap logo lockup (aperture glyph + wordmark). Single source of truth so the
 * brand reads identically in the app shell, public headers, and marketing pages.
 */
export function BrandMark({
  href,
  className,
  wordmarkClassName,
}: {
  /** When set, the mark is a link (e.g. "/" on public pages). */
  href?: string;
  className?: string;
  /** Override wordmark visibility, e.g. "hidden lg:inline" in a collapsed rail. */
  wordmarkClassName?: string;
}) {
  const content = (
    <>
      <span className="grid size-8 shrink-0 place-items-center rounded-lg bg-primary text-primary-foreground">
        <Aperture className="size-4" />
      </span>
      <span className={cn("truncate text-lg font-semibold tracking-tight", wordmarkClassName)}>
        ListSnap
      </span>
    </>
  );
  const classes = cn("flex min-w-0 items-center gap-2", className);

  return href ? (
    <Link href={href} className={classes} aria-label="ListSnap home">
      {content}
    </Link>
  ) : (
    <div className={classes}>{content}</div>
  );
}
