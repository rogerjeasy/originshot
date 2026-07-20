"use client";

import { Boxes } from "lucide-react";

import { useApiData } from "@/lib/use-api";
import type { LedgerAudit, LedgerEntryRow, LedgerStatus } from "@/lib/types";
import { AdaptiveChrome } from "@/components/adaptive-chrome";
import { FadeIn } from "@/components/motion/fade-in";
import { AuditStrip } from "@/components/ledger/audit-strip";
import { ChainEntries } from "@/components/ledger/chain-entries";
import { ChainHead } from "@/components/ledger/chain-head";
import { VerifyYourself } from "@/components/ledger/verify-yourself";
import { Alert } from "@/components/ui/alert";
import { Skeleton } from "@/components/ui/skeleton";

/**
 * The public transparency log.
 *
 * This page is a viewer, not evidence. Everything it renders it got from the
 * same server that wrote the log, so it is careful never to present itself as
 * verification — the verification story is the copy-pasteable command, which
 * recomputes everything locally against the public endpoints.
 *
 * That argument now drives the layout rather than sitting inside it. The old
 * page stacked four cards of identical weight, which flattened the distinction
 * between what we assert (head, entries, our own audit) and what a reader can
 * independently establish (the command). Here the ordering is the argument:
 * the head is published, the entries show the chain holding together, our own
 * audit is explicitly demoted, and the one block that inverts to ink is the only
 * one that constitutes proof.
 *
 * Widened from max-w-3xl: the fingerprint block and the chain rows both carry
 * 64-char hashes, and cramping them was what forced the old break-all mush.
 */
export default function LedgerPage() {
  const { data: status, loading } = useApiData<LedgerStatus>("/api/ledger");
  const { data: entries } = useApiData<LedgerEntryRow[]>("/api/ledger/entries?start=0&limit=50");
  // 404s until the first audit has run — a real, distinct state, so the strip
  // simply doesn't render rather than showing a default-green placeholder.
  const { data: audit } = useApiData<LedgerAudit>("/api/ledger/audit");

  const recent = entries ? [...entries].reverse() : [];

  return (
    <AdaptiveChrome ground="ink">
      <div className="mx-auto max-w-4xl px-4 py-12 sm:px-6 sm:py-16">
        <FadeIn className="mb-10">
          <p className="kicker t-verify inline-flex items-center gap-2">
            <Boxes className="size-3.5" aria-hidden />
            Append-only
          </p>
          <h1 className="display-face mt-4 text-[clamp(1.875rem,4.5vw,2.75rem)]">
            Transparency log
          </h1>
          <div className="mt-5 max-w-2xl space-y-3">
            <p className="text-[16.5px] leading-relaxed text-muted-foreground">
              Every manifest this instance issues is appended to a hash chain, and the head is
              published to Backblaze B2 as a checkpoint. Each entry commits to the one before it,
              so an entry can&apos;t be altered, reordered or removed without breaking every hash
              after it.
            </p>
            <p className="text-[15px] leading-relaxed text-muted-foreground">
              A per-file manifest proves how <em>that</em> file was made. It says nothing about
              what else was made — a product photo regenerated twelve times until an inconvenient
              scratch disappeared leaves no trace. This log is what closes that gap.
            </p>
          </div>
        </FadeIn>

        {loading ? (
          <div className="surface space-y-4">
            <Skeleton className="h-52 rounded-xl" />
            <Skeleton className="h-24 rounded-xl" />
          </div>
        ) : !status ? (
          <Alert className="surface" title="Couldn't reach the log">
            The service may be waking up — a first request can take up to a minute.
          </Alert>
        ) : (
          <FadeIn className="space-y-4">
            <ChainHead status={status} />
            {audit && <AuditStrip audit={audit} />}
            <VerifyYourself />
            <ChainEntries entries={recent} />
          </FadeIn>
        )}
      </div>
    </AdaptiveChrome>
  );
}
