import * as React from "react";

import { cn } from "@/lib/utils";

/** Image-shaped placeholder with a cool "developing" shimmer (see globals.css `.shimmer`). */
function Skeleton({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("shimmer rounded-lg bg-muted", className)} {...props} />;
}

export { Skeleton };
