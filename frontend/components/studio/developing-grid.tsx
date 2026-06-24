import { Sparkles } from "lucide-react";

import type { Style } from "@/lib/types";

/** Image-shaped "developing" placeholders shown while a generation job runs. */
export function DevelopingGrid({ styles }: { styles: Style[] }) {
  const tiles = styles.filter((s) => s !== "original" && s !== "video");
  const count = Math.max(tiles.length, 3);
  return (
    <section>
      <h2 className="mb-3 flex items-center gap-2 text-sm font-semibold uppercase tracking-wide text-muted-foreground">
        <Sparkles className="size-3.5 animate-pulse text-accent" />
        Developing…
      </h2>
      <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 xl:grid-cols-4">
        {Array.from({ length: count }).map((_, i) => (
          <div
            key={i}
            className="shimmer frame aspect-square w-full rounded-xl border bg-muted"
          />
        ))}
      </div>
    </section>
  );
}
