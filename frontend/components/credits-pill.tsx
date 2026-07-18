"use client";

import Link from "next/link";
import { Wallet } from "lucide-react";

import { cn } from "@/lib/utils";
import { useSession } from "@/lib/use-session";

/**
 * Balance indicator in the app header.
 *
 * Generation spends real money, so the balance belongs somewhere permanently visible rather
 * than behind a settings page — a user should never discover they're out of credit only
 * when a run is refused. Turns amber below the low-balance threshold the server reports,
 * so the warning level is defined in one place (config.low_balance_threshold) rather than
 * hardcoded here.
 */
export function CreditsPill() {
  const { credits, loading } = useSession();

  if (loading && !credits) {
    return <span className="h-7 w-20 animate-pulse rounded-full bg-muted" aria-hidden />;
  }
  if (!credits) return null;

  const held = credits.held_usd > 0;

  return (
    <Link
      href="/settings"
      title={
        held
          ? `$${credits.held_usd.toFixed(2)} is held by a running job`
          : "Credit balance — click for details"
      }
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs font-medium transition-colors",
        credits.low_balance
          ? "border-warning/30 bg-warning/10 text-warning"
          : "text-muted-foreground hover:bg-secondary hover:text-foreground",
      )}
    >
      <Wallet className="size-3.5" />
      <span className="tabular font-mono">${credits.balance_usd.toFixed(2)}</span>
      {held && (
        <span className="tabular font-mono opacity-60">
          −${credits.held_usd.toFixed(2)}
        </span>
      )}
    </Link>
  );
}
