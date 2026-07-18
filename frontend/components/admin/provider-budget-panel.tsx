"use client";

import { useState } from "react";
import { Info, Loader2, Save } from "lucide-react";

import { apiFetch } from "@/lib/api";
import { cn } from "@/lib/utils";
import type { ProviderBudget } from "@/lib/types";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";

/**
 * GMI Cloud credit position.
 *
 * IMPORTANT: this is not read from GMI. Their inference API has no balance endpoint, and
 * the console billing routes reject an inference key outright. So `remaining` is the
 * operator-recorded top-up minus the spend we metered from each step's real `cost_usd`.
 * The panel says so on its face — a number this load-bearing must not be mistaken for the
 * provider's own figure.
 */
export function ProviderBudgetPanel({
  budget,
  onChanged,
}: {
  budget: ProviderBudget;
  onChanged: () => void;
}) {
  const [value, setValue] = useState(
    budget.configured ? String(budget.budget_usd) : "",
  );
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function save() {
    const parsed = Number(value);
    if (!Number.isFinite(parsed) || parsed < 0) {
      setError("Enter the amount of GMI credit you purchased, in USD.");
      return;
    }
    setSaving(true);
    setError(null);
    try {
      await apiFetch("/api/admin/provider-budget", {
        method: "POST",
        body: JSON.stringify({ budget_usd: parsed }),
      });
      onChanged();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to save");
    } finally {
      setSaving(false);
    }
  }

  const pctUsed =
    budget.budget_usd > 0
      ? Math.min(100, (budget.metered_spend_usd / budget.budget_usd) * 100)
      : 0;
  const low = budget.configured && budget.remaining_usd < budget.budget_usd * 0.2;

  return (
    <Card>
      <CardHeader>
        <CardTitle>GMI Cloud credit</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        {budget.configured ? (
          <>
            <div className="grid grid-cols-3 gap-3">
              <div>
                <p className="text-xs uppercase tracking-wide text-muted-foreground">
                  Topped up
                </p>
                <p className="tabular text-2xl font-semibold tracking-tight">
                  ${budget.budget_usd.toFixed(2)}
                </p>
              </div>
              <div>
                <p className="text-xs uppercase tracking-wide text-muted-foreground">
                  Metered spend
                </p>
                <p className="tabular text-2xl font-semibold tracking-tight">
                  ${budget.metered_spend_usd.toFixed(4)}
                </p>
              </div>
              <div>
                <p className="text-xs uppercase tracking-wide text-muted-foreground">
                  Remaining
                </p>
                <p
                  className={cn(
                    "tabular text-2xl font-semibold tracking-tight",
                    low ? "text-warning" : "text-verified",
                  )}
                >
                  ${budget.remaining_usd.toFixed(2)}
                </p>
              </div>
            </div>

            <div
              className="h-1.5 w-full overflow-hidden rounded-full bg-muted"
              role="progressbar"
              aria-valuenow={Math.round(pctUsed)}
              aria-valuemin={0}
              aria-valuemax={100}
              aria-label="Provider credit consumed"
            >
              <div
                className={cn("h-full rounded-full", low ? "bg-warning" : "bg-accent")}
                style={{ width: `${pctUsed}%` }}
              />
            </div>
          </>
        ) : (
          <p className="text-sm text-muted-foreground">
            Record how much GMI credit you purchased to track spend against it.
          </p>
        )}

        <div className="flex items-end gap-2">
          <div className="flex-1 space-y-1.5">
            <label
              htmlFor="provider-budget"
              className="text-xs font-medium uppercase tracking-wide text-muted-foreground"
            >
              GMI credit purchased (USD)
            </label>
            <Input
              id="provider-budget"
              inputMode="decimal"
              value={value}
              onChange={(e) => setValue(e.target.value)}
              placeholder="e.g. 50.00"
            />
          </div>
          <Button variant="outline" onClick={() => void save()} disabled={saving}>
            {saving ? <Loader2 className="animate-spin" /> : <Save />}
            Save
          </Button>
        </div>

        {error && <p className="text-xs text-danger">{error}</p>}

        {/* The provenance of the number, stated on the surface that shows it. */}
        <p className="flex items-start gap-1.5 border-t pt-3 text-xs text-muted-foreground">
          <Info className="mt-0.5 size-3.5 shrink-0" />
          <span>{budget.source}</span>
        </p>
      </CardContent>
    </Card>
  );
}
