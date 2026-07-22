"use client";

import { useState } from "react";
import { Check, Copy } from "lucide-react";

import { API_BASE_URL } from "@/lib/api";
import { Card, CardContent } from "./ui/card";

/**
 * "Embed this badge" — turns a verified asset into something a seller can paste into a
 * listing, so the provenance shows up in the wild (where the buyer is), not only inside this
 * app. The badge is a live SVG served per request, so it always reflects the current ledger.
 *
 * The badge is an `<img>` (not an iframe) precisely so it renders in the many listing
 * surfaces that allow images but block frames.
 */
export function BadgeEmbed({ sha256 }: { sha256: string }) {
  const [copied, setCopied] = useState(false);

  const appOrigin =
    typeof window !== "undefined" ? window.location.origin : "https://originshot.vercel.app";
  const badgeSrc = `${API_BASE_URL}/api/badge/${sha256}.svg`;
  const verifyHref = `${appOrigin}/verify/${sha256}`;
  const snippet = `<a href="${verifyHref}"><img src="${badgeSrc}" alt="OriginShot provenance" height="20"></a>`;

  async function copy() {
    try {
      await navigator.clipboard.writeText(snippet);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      /* clipboard blocked — the snippet is selectable in the box below */
    }
  }

  return (
    <Card>
      <CardContent className="space-y-3 p-5">
        <div className="flex items-baseline justify-between gap-2">
          <p className="label text-muted-foreground">Embed this badge</p>
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src={badgeSrc} alt="OriginShot provenance badge" height={20} className="h-5" />
        </div>
        <p className="text-xs text-muted-foreground">
          Paste into a marketplace listing or product page. It resolves live against the
          transparency ledger, and links back here so a buyer can check it themselves.
        </p>
        <div className="flex items-stretch gap-2">
          <code className="min-w-0 flex-1 overflow-x-auto whitespace-nowrap rounded-md border bg-muted/50 px-3 py-2 font-mono text-[11px] text-muted-foreground">
            {snippet}
          </code>
          <button
            type="button"
            onClick={copy}
            aria-label="Copy embed code"
            className="inline-flex shrink-0 items-center gap-1.5 rounded-md border px-3 text-xs transition-colors hover:bg-secondary"
          >
            {copied ? <Check className="size-3.5 text-verified" /> : <Copy className="size-3.5" />}
            {copied ? "Copied" : "Copy"}
          </button>
        </div>
      </CardContent>
    </Card>
  );
}
