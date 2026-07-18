"use client";

import { useEffect, useState } from "react";
import { CheckCircle2, XCircle } from "lucide-react";

import { apiFetch } from "@/lib/api";
import { cn } from "@/lib/utils";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";

interface ComplianceCheck {
  name: string;
  passed: boolean;
  value?: string | number;
  threshold?: string | number;
  detail?: string;
}

interface ComplianceItem {
  marketplace: string;
  preset: string;
  passed: boolean;
  checks: ComplianceCheck[];
}

interface Compliance {
  source_style?: string | null;
  source_sha256?: string | null;
  items: ComplianceItem[];
}

const MARKET_LABEL: Record<string, string> = {
  amazon: "Amazon",
  etsy: "Etsy",
  shopify: "Shopify",
  ebay: "eBay",
  social: "Social",
};

/**
 * Marketplace readiness: the SKU's main image measured against each channel's rules by
 * the same renderer the export uses. Status is icon + text + colour, and the failing
 * check's numbers are shown — a red row tells the seller what to fix, not just "no".
 */
export function CompliancePanel({
  skuId,
  refreshKey,
}: {
  skuId: string;
  /** Bump when assets change so the scorecard re-measures against the new main image. */
  refreshKey: number;
}) {
  const [data, setData] = useState<Compliance | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    apiFetch<Compliance>(`/api/skus/${skuId}/compliance`)
      .then((d) => !cancelled && setData(d))
      .catch(() => !cancelled && setData(null)) // 400 = nothing to measure yet
      .finally(() => !cancelled && setLoading(false));
    return () => {
      cancelled = true;
    };
  }, [skuId, refreshKey]);

  if (!loading && !data) return null;

  return (
    <Card>
      <CardHeader>
        <CardTitle>Marketplace readiness</CardTitle>
      </CardHeader>
      <CardContent>
        {loading ? (
          <div className="space-y-2">
            {Array.from({ length: 5 }).map((_, i) => (
              <Skeleton key={i} className="h-6" />
            ))}
          </div>
        ) : data ? (
          <>
            <ul className="divide-y">
              {data.items.map((item) => {
                const failing = item.checks.filter((c) => !c.passed);
                return (
                  <li key={item.marketplace} className="flex items-start gap-2.5 py-2">
                    {item.passed ? (
                      <CheckCircle2 className="mt-0.5 size-4 shrink-0 text-verified" />
                    ) : (
                      <XCircle className="mt-0.5 size-4 shrink-0 text-warning" />
                    )}
                    <div className="min-w-0 flex-1">
                      <div className="flex items-baseline justify-between gap-2">
                        <span className="text-sm font-medium">
                          {MARKET_LABEL[item.marketplace] ?? item.marketplace}
                        </span>
                        <span
                          className={cn(
                            "shrink-0 text-xs",
                            item.passed ? "text-verified" : "text-warning",
                          )}
                        >
                          {item.passed ? "ready" : "check"}
                        </span>
                      </div>
                      {failing.map((c) => (
                        <p key={c.name} className="truncate font-mono text-[11px] text-muted-foreground">
                          {c.name}: {String(c.value ?? c.detail ?? "failed")}
                          {c.threshold != null ? ` (needs ${c.threshold})` : ""}
                        </p>
                      ))}
                    </div>
                  </li>
                );
              })}
            </ul>
            <p className="mt-2 border-t pt-2 text-[11px] text-muted-foreground">
              Measured on your {data.source_style === "studio" ? "studio image" : "photo"},
              rendered exactly as the export ships it.
            </p>
          </>
        ) : null}
      </CardContent>
    </Card>
  );
}
