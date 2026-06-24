import { ShieldCheck, Sparkles } from "lucide-react";

import { cn, shortHash } from "@/lib/utils";

/**
 * ListSnap's signature trust signal. Verified original = emerald + ShieldCheck;
 * AI-generated = neutral + Sparkles. Always icon + text + color, with a mono hash.
 */
export function ProvenanceBadge({
  authentic,
  sha,
  className,
}: {
  authentic: boolean;
  sha?: string | null;
  className?: string;
}) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs font-medium",
        authentic ? "border-transparent text-verified" : "border-transparent bg-secondary text-secondary-foreground",
        className,
      )}
      style={
        authentic
          ? { backgroundColor: "color-mix(in srgb, var(--color-verified) 12%, transparent)" }
          : undefined
      }
    >
      {authentic ? <ShieldCheck className="size-3.5" /> : <Sparkles className="size-3.5" />}
      <span>{authentic ? "Verified original" : "AI-generated"}</span>
      <span className="font-mono text-[11px] text-muted-foreground">{shortHash(sha)}</span>
    </span>
  );
}
