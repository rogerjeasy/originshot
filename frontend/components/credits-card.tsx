"use client";

import { Wallet } from "lucide-react";

import { cn } from "@/lib/utils";
import { useApiData } from "@/lib/use-api";
import { useSession } from "@/lib/use-session";
import type { LedgerEntry } from "@/lib/types";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";

const KIND_LABELS: Record<string, string> = {
  grant: "Credit added",
  hold: "Held for generation",
  debit: "Charged",
  refund: "Refunded",
  adjust: "Adjustment",
};

/**
 * The user's own credit position and recent transactions.
 *
 * Shows the hold/settle pair rather than a single net number, because that's what actually
 * happened: an estimate is reserved up front, then reconciled against the provider's real
 * cost. Collapsing it to one figure would hide why the balance moved twice per job.
 */
export function CreditsCard() {
  const { credits } = useSession();
  const { data: ledger, loading } = useApiData<LedgerEntry[]>("/api/credits/ledger?limit=8");

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Wallet className="size-4 t-accent" /> Credits
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        {!credits ? (
          <Skeleton className="h-16 w-full" />
        ) : (
          <>
            <div className="grid grid-cols-3 gap-3">
              <div>
                <p className="text-xs uppercase tracking-wide text-muted-foreground">
                  Balance
                </p>
                <p
                  className={cn(
                    "tabular text-2xl font-semibold tracking-tight",
                    credits.low_balance && "text-warning",
                  )}
                >
                  ${credits.balance_usd.toFixed(2)}
                </p>
              </div>
              <div>
                <p className="text-xs uppercase tracking-wide text-muted-foreground">Spent</p>
                <p className="tabular text-2xl font-semibold tracking-tight">
                  ${credits.spent_total_usd.toFixed(2)}
                </p>
              </div>
              <div>
                <p className="text-xs uppercase tracking-wide text-muted-foreground">
                  Today
                </p>
                <p className="tabular text-2xl font-semibold tracking-tight">
                  {credits.daily_used}
                  <span className="text-base text-muted-foreground">
                    /{credits.daily_quota}
                  </span>
                </p>
              </div>
            </div>

            {credits.held_usd > 0 && (
              <p className="text-xs text-muted-foreground">
                ${credits.held_usd.toFixed(2)} is currently held by a running job and will be
                reconciled against the provider&rsquo;s actual cost when it finishes.
              </p>
            )}
            {credits.low_balance && (
              <p className="text-xs text-warning">
                Your balance is running low — ask an admin to top it up before your next pack.
              </p>
            )}
          </>
        )}

        <div className="border-t pt-3">
          <p className="mb-1 text-xs font-medium uppercase tracking-wide text-muted-foreground">
            Recent activity
          </p>
          {loading ? (
            <Skeleton className="h-24 w-full" />
          ) : ledger && ledger.length > 0 ? (
            <ul className="divide-y">
              {ledger.map((e) => (
                <li key={e.id} className="flex items-baseline justify-between gap-3 py-2">
                  <span className="min-w-0 truncate text-sm">
                    {KIND_LABELS[e.kind] ?? e.kind}
                  </span>
                  <span
                    className={cn(
                      "tabular shrink-0 font-mono text-sm",
                      e.amount_usd > 0 ? "text-verified" : "text-muted-foreground",
                    )}
                  >
                    {e.amount_usd >= 0 ? "+" : "−"}${Math.abs(e.amount_usd).toFixed(4)}
                  </span>
                </li>
              ))}
            </ul>
          ) : (
            <p className="py-2 text-sm text-muted-foreground">No activity yet.</p>
          )}
        </div>
      </CardContent>
    </Card>
  );
}
