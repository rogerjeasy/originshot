import { Database, Sparkles } from "lucide-react";

import { cn } from "@/lib/utils";

/**
 * "Powered by" provenance strip. Genblaze orchestrates, Backblaze B2 stores, and a
 * fallback chain of providers generates — the exact stack the hackathon rewards.
 */
const PRIMARY = [
  { label: "Genblaze", icon: Sparkles, note: "orchestration" },
  { label: "Backblaze B2", icon: Database, note: "durable storage" },
];

const PROVIDERS = ["GMI Cloud", "OpenAI", "Google", "Luma"];

export function TrustStrip({ className }: { className?: string }) {
  return (
    <div className={cn("flex flex-col items-center gap-4", className)}>
      <p className="font-mono text-xs uppercase tracking-[0.2em] text-muted-foreground">
        Generated, verified &amp; stored on a production stack
      </p>
      <div className="flex flex-wrap items-center justify-center gap-2.5">
        {PRIMARY.map(({ label, icon: Icon, note }) => (
          <span
            key={label}
            className="inline-flex items-center gap-2 rounded-full border bg-card px-3.5 py-1.5 text-sm font-medium shadow-sm"
          >
            <Icon className="size-4 text-accent" />
            {label}
            <span className="hidden font-mono text-xs text-muted-foreground sm:inline">
              {note}
            </span>
          </span>
        ))}
        <span className="mx-1 hidden text-muted-foreground sm:inline">·</span>
        {PROVIDERS.map((p) => (
          <span
            key={p}
            className="inline-flex items-center rounded-full border bg-secondary/60 px-3 py-1.5 font-mono text-xs text-muted-foreground"
          >
            {p}
          </span>
        ))}
      </div>
    </div>
  );
}
