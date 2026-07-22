import { API_BASE_URL } from "@/lib/api";
import type { LedgerStatus } from "@/lib/types";

/**
 * The head of the chain, given the weight it actually carries.
 *
 * The old layout buried this hash in a third of a three-column grid cell, which
 * had it read as one statistic among several. It isn't: it is the single value
 * the whole page exists to publish, and the one thing a reader is meant to copy
 * and compare against a checkpoint they saved earlier.
 *
 * So it is set as a fingerprint block — eight groups of eight, the convention
 * for a checksum a human is expected to verify by eye. Grouping is what makes
 * "does this match what I saved?" answerable at a glance; an unbroken 64-char
 * run is not readable by a person, only by a diff.
 */
function Fingerprint({ hash }: { hash: string }) {
  const groups = hash.match(/.{1,8}/g) ?? [hash];
  return (
    <>
      {/* The grouping is a visual aid for eye-comparison. To a screen reader it
          is one value, not eight fragments, so the groups are hidden and the
          whole hash is announced once. */}
      <div
        aria-hidden
        className="grid grid-cols-4 gap-x-4 gap-y-1.5 font-mono text-[13px] leading-none sm:grid-cols-8 sm:gap-x-3"
      >
        {groups.map((g, i) => (
          <span key={i} className="tabular">
            {g}
          </span>
        ))}
      </div>
      <span className="sr-only">Current head hash {hash}</span>
    </>
  );
}

export function ChainHead({ status }: { status: LedgerStatus }) {
  const cp = status.checkpoint;

  return (
    <section className="surface overflow-hidden rounded-xl border bg-card">
      <div className="p-6 sm:p-7">
        <div className="flex flex-wrap items-baseline justify-between gap-x-6 gap-y-2">
          <p className="kicker t-verify">Current head</p>
          <p className="tabular font-mono text-xs text-muted-foreground">
            {status.size.toLocaleString()} {status.size === 1 ? "entry" : "entries"}
          </p>
        </div>
        <div className="mt-5">
          <Fingerprint hash={status.head} />
        </div>
      </div>

      {/* Facts about the head sit under a hairline rather than in their own
          cards — the head is the subject, these are its annotations. */}
      <dl className="grid gap-px border-t bg-border sm:grid-cols-3">
        <div className="bg-card p-5">
          <dt className="kicker text-muted-foreground">Published checkpoint</dt>
          <dd className="tabular mt-2 font-mono text-sm">
            {cp ? `${cp.size.toLocaleString()} entries` : "none yet"}
          </dd>
        </div>
        <div className="bg-card p-5">
          <dt className="kicker text-muted-foreground">Issued</dt>
          <dd className="mt-2 font-mono text-sm">{cp ? cp.issued_at : "—"}</dd>
        </div>
        <div className="bg-card p-5">
          <dt className="kicker text-muted-foreground">Uncommitted</dt>
          <dd
            className={`tabular mt-2 font-mono text-sm ${
              status.checkpoint_lag > 0 ? "text-warning" : ""
            }`}
          >
            {status.checkpoint_lag > 0
              ? `${status.checkpoint_lag} ${status.checkpoint_lag === 1 ? "entry" : "entries"}`
              : "none"}
          </dd>
        </div>
      </dl>

      {cp && (
        <div className="border-t bg-muted/40 px-5 py-4">
          <p className="kicker text-muted-foreground">Checkpoint hash</p>
          <p className="mt-1.5 break-all font-mono text-[12px] leading-relaxed">
            {cp.checkpoint_hash}
          </p>
          {cp.b2_key && (
            <p className="mt-2 break-all font-mono text-[11px] text-muted-foreground">
              published to B2 · {cp.b2_key}
            </p>
          )}
          {/* Assurances this published checkpoint carries, each shown only when genuinely
              present so the row never overstates. */}
          <div className="mt-2 flex flex-wrap gap-2">
            {cp.signature && (
              <span className="inline-flex items-center gap-1.5 rounded border border-verified/25 bg-verified-surface px-2 py-1 text-[11px] font-medium text-verified">
                <span aria-hidden>🖋</span>
                Ed25519-signed · key {cp.signature.key_id}
              </span>
            )}
            {cp.retained_until && (
              <span className="inline-flex items-center gap-1.5 rounded border border-verified/25 bg-verified-surface px-2 py-1 text-[11px] font-medium text-verified">
                <span aria-hidden>🔒</span>
                Immutable under B2 Object Lock until {cp.retained_until}
              </span>
            )}
            {/* The Bitcoin witness — an anchor the operator doesn't control. Green once
                confirmed on-chain; neutral while it's still a calendar commitment (which is
                honest: the proof exists, the block confirmation is pending). */}
            {cp.witness?.complete && cp.witness.bitcoin_block_height != null && (
              <span className="inline-flex items-center gap-1.5 rounded border border-verified/25 bg-verified-surface px-2 py-1 text-[11px] font-medium text-verified">
                <span aria-hidden>₿</span>
                Anchored in Bitcoin block {cp.witness.bitcoin_block_height.toLocaleString()}
              </span>
            )}
            {cp.witness && !cp.witness.complete && cp.witness.pending_calendars.length > 0 && (
              <span className="inline-flex items-center gap-1.5 rounded border px-2 py-1 text-[11px] font-medium text-muted-foreground">
                <span aria-hidden>₿</span>
                OpenTimestamps submitted · Bitcoin confirmation pending
              </span>
            )}
          </div>
          {cp.witness && (
            <p className="mt-2 text-[12px] leading-relaxed text-muted-foreground">
              Anchored into Bitcoin via OpenTimestamps — a timestamp we don&apos;t control.{" "}
              <a
                href={`${API_BASE_URL}/api/ledger/checkpoint.ots`}
                className="t-accent underline-offset-2 hover:underline"
              >
                Download the .ots proof
              </a>{" "}
              and run <code className="font-mono text-[11px]">ots verify</code> against Bitcoin
              yourself.
            </p>
          )}
          {status.checkpoint_lag > 0 && (
            <p className="mt-3 text-[13px] leading-relaxed text-muted-foreground">
              {status.checkpoint_lag} entr{status.checkpoint_lag === 1 ? "y has" : "ies have"} been
              appended since this head was published — present in the log, not yet committed to by
              a published checkpoint.
            </p>
          )}
        </div>
      )}
    </section>
  );
}
