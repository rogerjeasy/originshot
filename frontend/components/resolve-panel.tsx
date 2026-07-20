"use client";

import { useState } from "react";
import Link from "next/link";
import {
  AlertTriangle,
  ArrowUpRight,
  Check,
  Copy,
  Download,
  FileWarning,
  HelpCircle,
  PackageX,
  ScanLine,
  ShieldAlert,
  ShieldCheck,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";

import { cn } from "@/lib/utils";
import type { ResolveFinding, ResolveReport, ResolveSeverity } from "@/lib/types";
import { Badge } from "./ui/badge";
import { Card, CardContent } from "./ui/card";

/**
 * A Dispute Evidence Report.
 *
 * Reads top-down the way a decision gets made: the verdict, then the evidence that
 * produced it, then the document's own standing. Nothing is summarised away — the hashes
 * are shown in full because a third party arriving at this page has no reason to trust
 * our rendering of them, only the values themselves.
 *
 * Severity drives colour, never colour alone: every verdict carries an icon and words.
 */

const VERDICT: Record<ResolveFinding, { icon: LucideIcon; kicker: string }> = {
  listing_tampered: { icon: ShieldAlert, kicker: "Listing image altered after signing" },
  item_mismatch: { icon: PackageX, kicker: "Delivered item contradicts the listing" },
  condition_differences: { icon: FileWarning, kicker: "Right product, condition differs" },
  inconclusive: { icon: HelpCircle, kicker: "Evidence does not decide" },
  no_provenance: { icon: ScanLine, kicker: "No verifiable provenance" },
  provenance_only: { icon: ShieldCheck, kicker: "Provenance checked" },
  consistent: { icon: ShieldCheck, kicker: "Evidence agrees" },
};

const TONE: Record<ResolveSeverity, string> = {
  critical: "border-danger/25 bg-danger-surface text-danger",
  warning: "border-warning/25 bg-warning-surface text-warning",
  info: "border-info/25 bg-info-surface text-info",
  ok: "border-verified/25 bg-verified-surface text-verified",
};

const BADGE: Record<ResolveSeverity, "danger" | "warning" | "info" | "verified"> = {
  critical: "danger",
  warning: "warning",
  info: "info",
  ok: "verified",
};

function CopyHash({ value }: { value: string }) {
  const [copied, setCopied] = useState(false);
  return (
    <button
      type="button"
      onClick={() => {
        void navigator.clipboard?.writeText(value).then(() => {
          setCopied(true);
          setTimeout(() => setCopied(false), 1600);
        });
      }}
      className="inline-grid size-6 shrink-0 place-items-center rounded text-muted-foreground transition-colors hover:bg-secondary hover:text-foreground"
      aria-label={copied ? "Hash copied" : "Copy full hash"}
    >
      {copied ? <Check className="size-3.5 text-verified" /> : <Copy className="size-3.5" />}
    </button>
  );
}

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="grid grid-cols-[8.5rem_minmax(0,1fr)] items-start gap-3 px-4 py-2.5">
      <dt className="label pt-0.5 text-muted-foreground">{label}</dt>
      <dd className="min-w-0 font-mono text-xs">{children}</dd>
    </div>
  );
}

/** A hash that links into the public verifier — the chain is meant to be followed. */
function HashLink({ value }: { value: string }) {
  return (
    <span className="flex items-start gap-1.5">
      <Link
        href={`/verify/${value}`}
        className="inline-flex min-w-0 items-start gap-1 break-all t-accent underline decoration-accent/30 underline-offset-4 hover:decoration-accent"
      >
        <span className="min-w-0 break-all">{value}</span>
        <ArrowUpRight className="mt-px size-3.5 shrink-0" />
      </Link>
      <CopyHash value={value} />
    </span>
  );
}

export function ResolvePanel({ report }: { report: ResolveReport }) {
  const { icon: Icon, kicker } = VERDICT[report.finding] ?? VERDICT.inconclusive;
  const tone = TONE[report.severity] ?? TONE.info;
  const listing = report.listing;

  return (
    <div className="space-y-4">
      <Card className="overflow-hidden">
        {/* The verdict, stated before any evidence — this is what the reader came for. */}
        <div className={cn("flex items-start gap-3 border-b p-5", tone)}>
          <span className="mt-0.5 grid size-10 shrink-0 place-items-center rounded-md bg-card/60">
            <Icon className="size-5" />
          </span>
          <div className="min-w-0">
            <p className="label opacity-80">{kicker}</p>
            <p className="mt-1 font-semibold tracking-tight">{report.headline}</p>
          </div>
        </div>

        <div className="flex flex-wrap gap-2 border-b p-4">
          <Badge variant={BADGE[report.severity]} size="sm">
            <Icon /> {report.finding.replace(/_/g, " ")}
          </Badge>
          {listing.content_bound === false && (
            <Badge variant="danger" size="sm">
              <ShieldAlert /> Content binding broken
            </Badge>
          )}
          {listing.content_bound === true && (
            <Badge variant="verified" size="sm">
              <ShieldCheck /> Content-bound
            </Badge>
          )}
          {report.match && (
            <Badge variant="outline" size="sm">
              {report.match.score}/10 same product
            </Badge>
          )}
        </div>

        <p className="border-b p-4 text-sm leading-relaxed text-muted-foreground">
          {report.detail}
        </p>

        {/* The comparison, when one ran. Condition differences are the operative detail in
            most real disputes, so they get their own block rather than a footnote. */}
        {report.match ? (
          <div className="border-b p-4">
            <p className="label text-muted-foreground">Delivered-item comparison</p>
            <p className="mt-2 text-sm">{report.match.verdict}</p>
            {report.match.differences.length > 0 && (
              <div className="mt-3 rounded-md border border-warning/25 bg-warning-surface p-3">
                <p className="label flex items-center gap-1.5 text-warning">
                  <AlertTriangle className="size-3.5" />
                  Visible differences in condition or completeness
                </p>
                <ul className="mt-2 space-y-1 text-sm text-warning">
                  {report.match.differences.map((d) => (
                    <li key={d} className="flex gap-2">
                      <span aria-hidden>—</span>
                      <span className="min-w-0">{d}</span>
                    </li>
                  ))}
                </ul>
              </div>
            )}
            <p className="mt-3 font-mono text-[11px] text-muted-foreground">
              scored by {report.match.model} · vision-model judgement, evidence for a human
              decision
            </p>
          </div>
        ) : (
          report.match_unavailable && (
            <p className="border-b p-4 text-sm text-muted-foreground">
              No comparison was run — {report.match_unavailable}.
            </p>
          )
        )}

        <dl className="divide-y">
          {listing.sha256 && (
            <Row label="listing image">
              <HashLink value={listing.sha256} />
            </Row>
          )}
          {report.anchor?.sha256 && (
            <Row label="anchored original">
              <HashLink value={report.anchor.sha256} />
            </Row>
          )}
          {report.received?.sha256 && (
            <Row label="delivered photo">
              <span className="flex items-start gap-1.5">
                <span className="min-w-0 break-all">{report.received.sha256}</span>
                <CopyHash value={report.received.sha256} />
              </span>
            </Row>
          )}
          {listing.model && <Row label="listing model">{listing.model}</Row>}
          <Row label="report id">
            <span className="flex items-start gap-1.5">
              <span className="min-w-0 break-all">{report.id}</span>
              <CopyHash value={report.id} />
            </span>
          </Row>
          <Row label="issued">{report.issued_at}</Row>
        </dl>
      </Card>

      {report.report_url && (
        <Card>
          <CardContent className="flex flex-wrap items-center justify-between gap-3 p-4">
            <div className="min-w-0">
              <p className="text-sm font-medium">Signed-off PDF for the case file</p>
              <p className="mt-0.5 text-xs text-muted-foreground">
                Hash-anchored: this instance recorded the PDF&apos;s SHA-256, so a copy can be
                confirmed unaltered later.
              </p>
              {report.report_sha256 && (
                <p className="mt-1.5 break-all font-mono text-[11px] text-muted-foreground">
                  {report.report_sha256}
                </p>
              )}
            </div>
            <a
              href={report.report_url}
              className="inline-flex shrink-0 items-center gap-2 rounded-md border bg-card px-3 py-2 text-sm font-medium shadow-raised transition-colors hover:bg-secondary"
              download
            >
              <Download className="size-4" />
              Download report
            </a>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
