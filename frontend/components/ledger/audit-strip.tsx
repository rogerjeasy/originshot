import { AlertTriangle, ShieldCheck } from "lucide-react";

import type { LedgerAudit } from "@/lib/types";

/** "2h ago" — coarse on purpose; the exact timestamp sits alongside in mono. */
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
 * The auditor's heartbeat.
 *
 * Demoted from a full card to a strip on purpose. It previously sat at the same
 * visual weight as the "verify it yourself" block, which quietly argued that our
 * own agent checking our own storage is equivalent evidence to a reader
 * recomputing the chain independently. It isn't, and the page says so — so the
 * layout should not claim otherwise.
 *
 * Renders only once a pass has actually run; the endpoint 404s until then, and a
 * default-green placeholder would be a lie.
 */
export function AuditStrip({ audit }: { audit: LedgerAudit }) {
  const clean =
    audit.failures.length === 0 &&
    audit.assets_passed === audit.assets_sampled &&
    audit.chain_consistent !== false &&
    audit.checkpoint_reproduced !== false;

  const facts: [string, string, boolean?][] = [
    ["assets", `${audit.assets_passed}/${audit.assets_sampled} passed`, audit.assets_passed !== audit.assets_sampled],
    ["replay", audit.chain_consistent === false ? "BROKEN" : "consistent", audit.chain_consistent === false],
    [
      "head",
      audit.checkpoint_reproduced === false
        ? "NOT REPRODUCED"
        : audit.checkpoint_reproduced === true
          ? "reproduced"
          : "first pass",
      audit.checkpoint_reproduced === false,
    ],
  ];

  return (
    <section className="surface overflow-hidden rounded-xl border bg-card">
      <div className="flex flex-wrap items-center justify-between gap-x-4 gap-y-2 px-5 py-4">
        <p className="flex items-center gap-2 text-[13.5px] font-medium">
          {clean ? (
            <ShieldCheck className="size-4 text-verified" aria-hidden />
          ) : (
            <AlertTriangle className="size-4 text-danger" aria-hidden />
          )}
          Self-audit {clean ? "passed" : "reported failures"}
          <span className="font-normal text-muted-foreground">
            · {relativeTime(audit.finished_at)}
          </span>
        </p>
        <dl className="flex flex-wrap items-baseline gap-x-5 gap-y-1">
          {facts.map(([k, v, bad]) => (
            <div key={k} className="flex items-baseline gap-2">
              <dt className="kicker text-muted-foreground">{k}</dt>
              <dd className={`tabular font-mono text-[12px] ${bad ? "text-danger" : ""}`}>{v}</dd>
            </div>
          ))}
        </dl>
      </div>

      {audit.failures.length > 0 && (
        <ul className="border-t">
          {audit.failures.map((f) => (
            <li
              key={f.sha256}
              className="break-all border-b px-5 py-2.5 font-mono text-[11.5px] leading-relaxed text-danger last:border-b-0"
            >
              {f.sha256} — {f.error ?? "stored bytes no longer match the record"}
            </li>
          ))}
        </ul>
      )}

      <p className="border-t bg-muted/40 px-5 py-3.5 text-[12.5px] leading-relaxed text-muted-foreground">
        Every few hours this instance re-downloads a random sample of its own stored media,
        re-derives each file&apos;s integrity from bytes alone, replays the chain against the last
        published head, and commits a fresh checkpoint.
        {audit.b2_key && (
          <>
            {" "}
            Report on B2 · <span className="font-mono">{audit.b2_key}</span>.
          </>
        )}{" "}
        <strong className="font-medium text-foreground">It audits itself</strong> — independent
        verification is the command below.
      </p>
    </section>
  );
}
