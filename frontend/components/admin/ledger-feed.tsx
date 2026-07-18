"use client";

import { cn } from "@/lib/utils";
import type { LedgerEntry, LedgerKind } from "@/lib/types";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

const KIND_LABELS: Record<LedgerKind, string> = {
  grant: "Grant",
  hold: "Held",
  debit: "Debit",
  refund: "Refund",
  adjust: "Adjust",
};

/**
 * Credit transaction feed.
 *
 * Amounts are signed by the server (negative = money leaving the balance), so the sign is
 * displayed as-is rather than being re-derived from the kind — the ledger is the authority
 * on direction, and a UI that recomputed it could disagree with the stored row.
 */
export function LedgerFeed({ entries }: { entries: LedgerEntry[] }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Credit ledger</CardTitle>
      </CardHeader>
      <CardContent>
        <ul className="divide-y">
          {entries.map((e) => (
            <li key={e.id} className="flex items-center gap-3 py-2.5">
              <span
                className={cn(
                  "shrink-0 rounded-full px-2 py-0.5 text-xs font-medium",
                  e.kind === "grant" && "bg-verified/12 text-verified",
                  e.kind === "refund" && "bg-accent/12 text-accent",
                  e.kind === "hold" && "bg-secondary text-secondary-foreground",
                  e.kind === "debit" && "bg-secondary text-secondary-foreground",
                  e.kind === "adjust" && "bg-warning/12 text-warning",
                )}
              >
                {KIND_LABELS[e.kind]}
              </span>

              <div className="min-w-0 flex-1">
                <p className="truncate text-sm">{e.note ?? "—"}</p>
                <p className="truncate font-mono text-xs text-muted-foreground">{e.uid}</p>
              </div>

              <div className="shrink-0 text-right">
                <p
                  className={cn(
                    "tabular font-mono text-sm font-medium",
                    e.amount_usd > 0 ? "text-verified" : "text-muted-foreground",
                  )}
                >
                  {e.amount_usd >= 0 ? "+" : "−"}${Math.abs(e.amount_usd).toFixed(4)}
                </p>
                <p className="tabular font-mono text-xs text-muted-foreground">
                  → ${e.balance_after.toFixed(2)}
                </p>
              </div>
            </li>
          ))}
        </ul>

        {entries.length === 0 && (
          <p className="py-6 text-center text-sm text-muted-foreground">
            No credit activity yet.
          </p>
        )}
      </CardContent>
    </Card>
  );
}
