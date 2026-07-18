import * as React from "react";

import { cn } from "@/lib/utils";

/**
 * Placeholders where media will land are image-shaped and "develop" — a print
 * coming up in the tray. Text placeholders are plain bars.
 */
function Skeleton({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return <div aria-hidden className={cn("developing rounded-md bg-muted", className)} {...props} />;
}

/** Image-shaped variant: keeps the frame motif so the grid never reflows. */
function MediaSkeleton({
  className,
  aspect = "aspect-square",
  ...props
}: React.HTMLAttributes<HTMLDivElement> & { aspect?: string }) {
  return (
    <div
      aria-hidden
      className={cn("developing frame w-full rounded-md border bg-muted", aspect, className)}
      {...props}
    />
  );
}

export { Skeleton, MediaSkeleton };
