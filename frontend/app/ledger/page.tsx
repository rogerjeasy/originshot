"use client";

import { Boxes, Terminal } from "lucide-react";

import { useApiData } from "@/lib/use-api";
import type { LedgerEntryRow, LedgerStatus } from "@/lib/types";
import { AdaptiveChrome } from "@/components/adaptive-chrome";
import { FadeIn } from "@/components/motion/fade-in";
import { Alert } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";

/**
 * The public transparency log.
 *
 * This page is a viewer, not evidence. Anything it renders it got from the same server that
 * wrote the log, so the page is careful never to present itself as verification — the
 * verification story is the copy-pasteable command, which recomputes everything locally
 * against the public endpoints. Saying that plainly is the point of the feature.
 */
export default function LedgerPage() {
  const { data: status, loading } = useApiData<LedgerStatus>("/api/ledger");
  const { data: entries } = useApiData<LedgerEntryRow[]>(
    "/api/ledger/entries?start=0&limit=50",
  );

  const recent = entries ? [...entries].reverse() : [];

  return (
    <AdaptiveChrome>
      <div className="mx-auto max-w-3xl px-4 py-12 sm:px-6 sm:py-16">
        <FadeIn className="mb-8">
          <span className="grid size-11 place-items-center rounded-md border bg-card text-accent shadow-raised">
            <Boxes className="size-5" />
          </span>
          <h1 className="mt-5 text-3xl font-semibold tracking-[-0.03em]">
            Transparency log
          </h1>
          <p className="mt-3 text-muted-foreground">
            Every manifest this instance issues is appended to a hash chain, and the head is
            published to Backblaze B2 as a checkpoint. Each entry commits to the one before
            it, so an entry can&apos;t be altered, reordered or removed without breaking
            every hash after it.
          </p>
          <p className="mt-3 text-muted-foreground">
            A per-file manifest proves how <em>that</em> file was made. It says nothing about
            what else was made — a product photo regenerated twelve times until an
            inconvenient scratch disappeared leaves no trace. This log is what closes that
            gap.
          </p>
        </FadeIn>

        {loading ? (
          <Skeleton className="h-28 rounded-lg" />
        ) : !status ? (
          <Alert title="Couldn&apos;t reach the log">
            The service may be waking up — a first request can take up to a minute.
          </Alert>
        ) : (
          <FadeIn className="space-y-4">
            <Card>
              <CardContent className="grid gap-4 p-5 sm:grid-cols-3">
                <div>
                  <p className="label text-muted-foreground">Entries</p>
                  <p className="tabular mt-1 text-2xl font-semibold">{status.size}</p>
                </div>
                <div className="sm:col-span-2">
                  <p className="label text-muted-foreground">Current head</p>
                  <p className="mt-1 break-all font-mono text-xs">{status.head}</p>
                </div>
                {status.checkpoint && (
                  <div className="sm:col-span-3">
                    <p className="label text-muted-foreground">
                      Latest checkpoint · {status.checkpoint.size} entries ·{" "}
                      {status.checkpoint.issued_at}
                    </p>
                    <p className="mt-1 break-all font-mono text-xs">
                      {status.checkpoint.checkpoint_hash}
                    </p>
                    {status.checkpoint.b2_key && (
                      <p className="mt-1 break-all font-mono text-[11px] text-muted-foreground">
                        published to B2 · {status.checkpoint.b2_key}
                      </p>
                    )}
                    {status.checkpoint_lag > 0 && (
                      <p className="mt-2 text-sm text-muted-foreground">
                        {status.checkpoint_lag} entr
                        {status.checkpoint_lag === 1 ? "y" : "ies"} appended since — in the
                        log, not yet committed to by a published head.
                      </p>
                    )}
                  </div>
                )}
              </CardContent>
            </Card>

            {/* The actual verification story. Deliberately more prominent than the table. */}
            <Card>
              <CardContent className="p-5">
                <p className="flex items-center gap-2 text-sm font-medium">
                  <Terminal className="size-4 text-accent" /> Don&apos;t take our word for it
                </p>
                <p className="mt-2 text-sm text-muted-foreground">
                  This page is rendered by the same server that wrote the log, so it proves
                  nothing on its own. The verifier below talks only to the public endpoints
                  and recomputes every hash locally.
                </p>
                <pre className="mt-3 overflow-x-auto rounded-md border bg-muted p-3 font-mono text-xs">
                  python scripts/verify_ledger.py --save checkpoint.json{"\n"}
                  {"# ...later..."}{"\n"}
                  python scripts/verify_ledger.py --against checkpoint.json
                </pre>
                <p className="mt-3 text-sm text-muted-foreground">
                  Saving a checkpoint and re-checking later is the strongest guarantee
                  available here: it proves the log only ever grew. It is not signed, and a
                  single-operator log can&apos;t rule out showing a different chain to
                  someone else — that needs independent witnesses, which we don&apos;t have.
                </p>
              </CardContent>
            </Card>

            <Card>
              <CardContent className="p-0">
                <p className="label border-b px-4 py-3 text-muted-foreground">
                  Most recent entries
                </p>
                <ul className="divide-y">
                  {recent.map((entry) => (
                    <li key={entry.entry_hash} className="px-4 py-3">
                      <div className="flex flex-wrap items-baseline gap-2">
                        <span className="tabular font-mono text-xs text-muted-foreground">
                          #{entry.seq}
                        </span>
                        <Badge
                          variant={entry.kind === "original" ? "verified" : "outline"}
                          size="sm"
                        >
                          {entry.kind}
                        </Badge>
                        <span className="font-mono text-[11px] text-muted-foreground">
                          {entry.recorded_at}
                        </span>
                      </div>
                      <p className="mt-1 break-all font-mono text-xs">
                        {entry.subject_sha256}
                      </p>
                    </li>
                  ))}
                </ul>
              </CardContent>
            </Card>
          </FadeIn>
        )}
      </div>
    </AdaptiveChrome>
  );
}
