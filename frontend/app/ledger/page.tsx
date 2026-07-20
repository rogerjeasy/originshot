"use client";

import { AlertTriangle, Boxes, ShieldCheck, Terminal } from "lucide-react";

import { useApiData } from "@/lib/use-api";
import type { LedgerAudit, LedgerEntryRow, LedgerStatus } from "@/lib/types";
import { AdaptiveChrome } from "@/components/adaptive-chrome";
import { FadeIn } from "@/components/motion/fade-in";
import { Alert } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";

/** "2h ago" from an ISO timestamp — coarse on purpose; the exact time is shown alongside. */
function relativeTime(iso: string): string {
  const ms = Date.now() - new Date(iso).getTime();
  if (Number.isNaN(ms) || ms < 0) return iso;
  const mins = Math.floor(ms / 60_000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.floor(mins / 60);
  if (hours < 48) return `${hours}h ago`;
  return `${Math.floor(hours / 24)}d ago`;
}

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
  // 404 until the first audit has run — a real, distinct state, so the card simply
  // doesn't render rather than showing a default-green placeholder.
  const { data: audit } = useApiData<LedgerAudit>("/api/ledger/audit");

  const recent = entries ? [...entries].reverse() : [];
  const auditClean =
    audit &&
    audit.failures.length === 0 &&
    audit.assets_passed === audit.assets_sampled &&
    audit.chain_consistent !== false &&
    audit.checkpoint_reproduced !== false;

  return (
    <AdaptiveChrome>
      <div className="mx-auto max-w-3xl px-4 py-12 sm:px-6 sm:py-16">
        <FadeIn className="mb-8">
          <p className="kicker t-verify inline-flex items-center gap-2">
            <Boxes className="size-3.5" />
            Append-only
          </p>
          <h1 className="display-face mt-4 text-[clamp(1.875rem,4.5vw,2.5rem)]">
            Transparency log
          </h1>
          <p className="mt-4 text-[16.5px] leading-relaxed text-muted-foreground">
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

            {/* The Auditor's heartbeat: the scheduled agent that re-verifies stored bytes
                and replays this chain. Renders only once a pass has actually run. */}
            {audit && (
              <Card>
                <CardContent className="p-5">
                  <div className="flex flex-wrap items-baseline justify-between gap-2">
                    <p className="flex items-center gap-2 text-sm font-medium">
                      {auditClean ? (
                        <ShieldCheck className="size-4 text-verified" />
                      ) : (
                        <AlertTriangle className="size-4 text-danger" />
                      )}
                      Last audit · {relativeTime(audit.finished_at)}
                    </p>
                    <span className="font-mono text-[11px] text-muted-foreground">
                      {audit.finished_at}
                    </span>
                  </div>
                  <div className="mt-3 grid gap-3 sm:grid-cols-3">
                    <div>
                      <p className="label text-muted-foreground">Assets re-verified</p>
                      <p className="tabular mt-1 font-mono text-sm">
                        {audit.assets_passed} / {audit.assets_sampled} passed
                      </p>
                    </div>
                    <div>
                      <p className="label text-muted-foreground">Chain replay</p>
                      <p className="mt-1 font-mono text-sm">
                        {audit.chain_consistent === false ? "BROKEN" : "consistent"}
                      </p>
                    </div>
                    <div>
                      <p className="label text-muted-foreground">Published head</p>
                      <p className="mt-1 font-mono text-sm">
                        {audit.checkpoint_reproduced === false
                          ? "NOT REPRODUCED"
                          : audit.checkpoint_reproduced === true
                            ? "reproduced"
                            : "first pass"}
                      </p>
                    </div>
                  </div>
                  {audit.failures.length > 0 && (
                    <ul className="mt-3 space-y-1">
                      {audit.failures.map((f) => (
                        <li key={f.sha256} className="break-all font-mono text-xs text-danger">
                          ✗ {f.sha256} {f.error ?? "— stored bytes no longer match the record"}
                        </li>
                      ))}
                    </ul>
                  )}
                  <p className="mt-3 text-xs text-muted-foreground">
                    Every few hours this instance re-downloads a random sample of its own
                    stored media, re-derives each file&apos;s integrity from bytes alone,
                    replays this chain against the last published head, and commits a fresh
                    checkpoint. {audit.b2_key && <>Report on B2 · <span className="font-mono">{audit.b2_key}</span>.</>}{" "}
                    It audits itself — independent verification is the command below.
                  </p>
                </CardContent>
              </Card>
            )}

            {/* The actual verification story. Deliberately more prominent than the table. */}
            <Card>
              <CardContent className="p-5">
                <p className="flex items-center gap-2 text-sm font-medium">
                  <Terminal className="size-4 t-accent" /> Don&apos;t take our word for it
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
