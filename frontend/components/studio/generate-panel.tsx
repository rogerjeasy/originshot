"use client";

import { useEffect, useState } from "react";
import { Download, Loader2, Wallet, Wand2 } from "lucide-react";

import { apiFetch } from "@/lib/api";
import type { CostEstimate, Job, Marketplace, Style } from "@/lib/types";
import { MarketplacePicker } from "@/components/marketplace-picker";
import { StylePicker } from "@/components/style-picker";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="space-y-2">
      <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">{label}</p>
      {children}
    </div>
  );
}

/** Generation controls: style + marketplace pickers, generate/export actions, job status. */
export function GeneratePanel({
  styles,
  onStylesChange,
  marketplaces,
  onMarketplacesChange,
  hasOriginal,
  busy,
  onGenerate,
  canExport,
  onExport,
  exporting = false,
  job,
}: {
  styles: Style[];
  onStylesChange: (s: Style[]) => void;
  marketplaces: Marketplace[];
  onMarketplacesChange: (m: Marketplace[]) => void;
  hasOriginal: boolean;
  busy: boolean;
  onGenerate: () => void;
  canExport: boolean;
  onExport: () => void;
  exporting?: boolean;
  job: Job | null;
}) {
  // Image-to-video is chained off the studio hero shot, so video without studio always
  // fails server-side (generation.py). Surface the dependency instead of failing late.
  const videoNeedsStudio = styles.includes("video") && !styles.includes("studio");

  // Quote the selection before the user commits. Re-quoted server-side on submit — this is
  // for informed consent, not enforcement.
  const [quote, setQuote] = useState<CostEstimate | null>(null);
  useEffect(() => {
    if (styles.length === 0) {
      setQuote(null);
      return;
    }
    let cancelled = false;
    const params = styles.map((s) => `styles=${encodeURIComponent(s)}`).join("&");
    apiFetch<CostEstimate>(`/api/credits/estimate?${params}`)
      .then((q) => !cancelled && setQuote(q))
      .catch(() => !cancelled && setQuote(null));
    return () => {
      cancelled = true;
    };
  }, [styles]);

  const unaffordable = quote != null && !quote.affordable;

  return (
    <Card>
      <CardHeader>
        <CardTitle>Generate</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <Field label="Styles">
          <StylePicker value={styles} onChange={onStylesChange} />
        </Field>
        <Field label="Marketplaces">
          <MarketplacePicker value={marketplaces} onChange={onMarketplacesChange} />
        </Field>

        {videoNeedsStudio && (
          <p className="text-xs text-warning">
            Video is generated from the studio shot — add <strong>Studio</strong> to your
            selection.
          </p>
        )}

        {/* The quote is a ceiling: the run is held against it and refunded down to the
            provider's actual cost, so it can only ever come in at or under this. */}
        {quote && (
          <div className="rounded-lg border bg-secondary/40 p-3">
            <div className="flex items-baseline justify-between gap-2">
              <span className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                Estimated cost
              </span>
              <span className="tabular font-mono text-sm font-semibold">
                ${quote.total_estimate_usd.toFixed(2)}
              </span>
            </div>
            <div className="mt-1 flex items-baseline justify-between gap-2 text-xs text-muted-foreground">
              <span>~{Math.round(quote.eta_seconds / 6) / 10} min</span>
              <span className="tabular font-mono">
                balance ${quote.balance_usd.toFixed(2)}
              </span>
            </div>
          </div>
        )}

        <Button
          variant="accent"
          className="w-full"
          disabled={
            !hasOriginal || styles.length === 0 || busy || videoNeedsStudio || unaffordable
          }
          onClick={onGenerate}
        >
          {busy ? <Loader2 className="animate-spin" /> : <Wand2 />}
          {busy ? "Generating…" : "Generate pack"}
        </Button>

        {!hasOriginal && <p className="text-xs text-muted-foreground">Upload a photo first.</p>}
        {unaffordable && (
          <p className="flex items-start gap-1.5 text-xs text-warning">
            <Wallet className="mt-0.5 size-3.5 shrink-0" />
            Not enough credit for this pack — reduce the styles selected or ask an admin to
            top up your balance.
          </p>
        )}
        {job?.status === "done" && typeof job.cost_actual === "number" && (
          <p className="font-mono text-xs text-muted-foreground">
            actual cost ${job.cost_actual.toFixed(4)}
          </p>
        )}
        {job?.status === "partial" && (
          <p className="text-xs text-warning">
            Some styles fell back or failed — partial pack delivered.
          </p>
        )}

        <Button
          variant="outline"
          className="w-full"
          disabled={!canExport || exporting}
          onClick={onExport}
        >
          {exporting ? <Loader2 className="animate-spin" /> : <Download />}
          {exporting ? "Building ZIP…" : "Export pack (.zip)"}
        </Button>
      </CardContent>
    </Card>
  );
}
