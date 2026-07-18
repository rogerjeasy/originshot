"use client";

import { useEffect, useState } from "react";
import { Check, Copy, Loader2, PenLine } from "lucide-react";

import { apiFetch } from "@/lib/api";
import type { Listing, ListingEntry, Marketplace } from "@/lib/types";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";

const MARKET_LABEL: Record<string, string> = {
  amazon: "Amazon",
  etsy: "Etsy",
  shopify: "Shopify",
  ebay: "eBay",
  social: "Social",
};

function CopyButton({ text, label }: { text: string; label: string }) {
  const [copied, setCopied] = useState(false);
  return (
    <button
      type="button"
      className="inline-flex items-center gap-1 rounded-md px-1.5 py-0.5 text-xs text-muted-foreground transition-colors hover:text-foreground"
      onClick={async () => {
        await navigator.clipboard.writeText(text);
        setCopied(true);
        setTimeout(() => setCopied(false), 1500);
      }}
      aria-label={`Copy ${label}`}
    >
      {copied ? <Check className="size-3 text-verified" /> : <Copy className="size-3" />}
      {copied ? "Copied" : "Copy"}
    </button>
  );
}

function EntryView({ entry }: { entry: ListingEntry }) {
  const fullText = [
    entry.title,
    "",
    ...entry.bullets.map((b) => `- ${b}`),
    entry.bullets.length ? "" : null,
    entry.description,
    entry.keywords.length ? "" : null,
    entry.keywords.length ? entry.keywords.join(", ") : null,
  ]
    .filter((l): l is string => l !== null)
    .join("\n");

  return (
    <div className="space-y-4 pt-4">
      <div>
        <div className="flex items-baseline justify-between gap-2">
          <p className="label text-muted-foreground">Title</p>
          <span className="tabular font-mono text-[11px] text-muted-foreground">
            {entry.title.length}/{entry.title_max}
          </span>
        </div>
        <p className="mt-1 text-sm font-medium">{entry.title}</p>
      </div>

      {entry.bullets.length > 0 && (
        <div>
          <p className="label text-muted-foreground">Bullets</p>
          <ul className="mt-1 space-y-1">
            {entry.bullets.map((b) => (
              <li key={b} className="flex gap-2 text-sm">
                <span className="text-muted-foreground">–</span>
                <span className="min-w-0">{b}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      <div>
        <p className="label text-muted-foreground">Description</p>
        <p className="mt-1 whitespace-pre-wrap text-sm text-muted-foreground">
          {entry.description}
        </p>
      </div>

      {entry.keywords.length > 0 && (
        <div>
          <p className="label text-muted-foreground">Keywords</p>
          <div className="mt-1.5 flex flex-wrap gap-1.5">
            {entry.keywords.map((k) => (
              <span
                key={k}
                className="rounded-full border bg-muted px-2 py-0.5 font-mono text-[11px] text-muted-foreground"
              >
                {k}
              </span>
            ))}
          </div>
        </div>
      )}

      <div className="flex justify-end border-t pt-3">
        <CopyButton text={fullText} label="full listing copy" />
      </div>
    </div>
  );
}

/**
 * Listing copy for the SKU: one chat-model call, per-marketplace tabs, hard limits
 * enforced server-side. Copy carries its own disclosure line — it ships in the export
 * pack, so it discloses itself the same way the images do.
 */
export function ListingPanel({
  skuId,
  marketplaces,
}: {
  skuId: string;
  /** The channels currently selected in the generate panel; empty ⇒ all channels. */
  marketplaces: Marketplace[];
}) {
  const [listing, setListing] = useState<Listing | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    apiFetch<Listing>(`/api/skus/${skuId}/listing`)
      .then((l) => !cancelled && setListing(l))
      .catch(() => undefined); // 404 just means nothing generated yet
    return () => {
      cancelled = true;
    };
  }, [skuId]);

  async function generate() {
    setBusy(true);
    setError(null);
    try {
      // No channel selection ⇒ the three core channels rather than all five: a five-channel
      // completion runs long enough to trip proxy timeouts. Rewrite with channels selected
      // to target others.
      const wanted = marketplaces.length > 0 ? marketplaces : ["amazon", "etsy", "social"];
      const l = await apiFetch<Listing>(`/api/skus/${skuId}/listing`, {
        method: "POST",
        body: JSON.stringify({ marketplaces: wanted }),
      });
      setListing(l);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Copy generation failed");
    } finally {
      setBusy(false);
    }
  }

  const channels = listing ? Object.keys(listing.marketplaces) : [];

  return (
    <Card>
      <CardHeader className="flex-row items-center justify-between space-y-0">
        <CardTitle>Listing copy</CardTitle>
        <Button variant="outline" size="sm" disabled={busy} onClick={generate}>
          {busy ? <Loader2 className="animate-spin" /> : <PenLine />}
          {busy ? "Writing…" : listing ? "Rewrite" : "Write listing copy"}
        </Button>
      </CardHeader>
      <CardContent>
        {error && <Alert className="mb-4">{error}</Alert>}

        {!listing ? (
          <p className="text-sm text-muted-foreground">
            Titles, bullets, and descriptions written to each marketplace&apos;s rules —
            from your product facts, never invented claims. Ships in the export pack.
          </p>
        ) : (
          <>
            <Tabs defaultValue={channels[0]}>
              <TabsList>
                {channels.map((m) => (
                  <TabsTrigger key={m} value={m}>
                    {MARKET_LABEL[m] ?? m}
                  </TabsTrigger>
                ))}
              </TabsList>
              {channels.map((m) => (
                <TabsContent key={m} value={m}>
                  <EntryView entry={listing.marketplaces[m]} />
                </TabsContent>
              ))}
            </Tabs>
            <p className="mt-4 border-t pt-3 font-mono text-[11px] leading-relaxed text-muted-foreground">
              {listing.disclosure}
            </p>
          </>
        )}
      </CardContent>
    </Card>
  );
}
