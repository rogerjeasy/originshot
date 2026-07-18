import { ShieldCheck, Sparkles } from "lucide-react";

import { cn, shortHash } from "@/lib/utils";

/**
 * The trust signal, reused wherever media appears.
 *
 * Verified original = patch-14 green + ShieldCheck. AI-generated = neutral ink
 * + Sparkles. Never colour alone: the icon and the word carry the meaning for
 * anyone who can't separate the two hues.
 *
 * The hash is set in mono because it is machine-true — that typographic split
 * between "what we claim" and "what can be checked" runs through the whole app.
 */
export function ProvenanceBadge({
  authentic,
  sha,
  compact,
  className,
}: {
  authentic: boolean;
  sha?: string | null;
  /** Drops the wordmark, keeping icon + hash. For dense tile corners. */
  compact?: boolean;
  className?: string;
}) {
  return (
    <span
      className={cn(
        "inline-flex max-w-full items-center gap-1.5 rounded-full border px-2 py-1 text-[11px] font-medium",
        authentic
          ? "border-verified/25 bg-verified-surface text-verified"
          : "border-border bg-card text-muted-foreground",
        className,
      )}
    >
      {authentic ? (
        <ShieldCheck className="size-3.5 shrink-0" />
      ) : (
        <Sparkles className="size-3.5 shrink-0" />
      )}
      {!compact && (
        <span className="truncate">{authentic ? "Verified original" : "AI-generated"}</span>
      )}
      {sha && (
        <span
          className={cn(
            "truncate font-mono tracking-tight",
            authentic ? "text-verified/75" : "text-muted-foreground/75",
          )}
        >
          {shortHash(sha)}
        </span>
      )}
    </span>
  );
}
