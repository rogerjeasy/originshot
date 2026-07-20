import Link from "next/link";
import { ArrowUpRight } from "lucide-react";

import type { LedgerEntryRow } from "@/lib/types";

/** First 10 of a hash — enough to compare by eye, short enough to sit inline. */
const short = (h: string) => h.slice(0, 10);

/**
 * The log rendered as the structure it actually is.
 *
 * The previous version was a flat <ul> of hashes, which threw away the only
 * interesting property of the data: every entry commits to the one before it via
 * `prev_hash`. That linkage is the entire security argument of the page, and it
 * was invisible. Here each row shows the hash it inherits and the hash it
 * produces, joined down a continuous spine — so "an entry can't be altered,
 * reordered or removed without breaking every hash after it" is something you
 * can see rather than a sentence you're asked to accept.
 *
 * Note this deliberately does the opposite of `RunLedger`, which had its spine
 * removed because a full-width rule between stages already carried the
 * relationship. Here the relationship *between adjacent rows* is the subject, so
 * the spine is the content, not decoration.
 */
export function ChainEntries({ entries }: { entries: LedgerEntryRow[] }) {
  if (entries.length === 0) {
    return (
      <section className="surface rounded-xl border bg-card">
        <p className="kicker border-b px-5 py-3.5 text-muted-foreground">Most recent entries</p>
        {/* Not `.grain` — that motif's dot colour is --ink-fg, so it is
            invisible on a paper-ground card. It belongs to ink bands only. */}
        <div className="bg-muted/40 px-5 py-14 text-center">
          <p className="text-sm text-muted-foreground">
            Nothing appended yet. The first generated asset writes entry #0.
          </p>
        </div>
      </section>
    );
  }

  return (
    <section className="surface overflow-hidden rounded-xl border bg-card">
      <div className="flex flex-wrap items-baseline justify-between gap-x-6 gap-y-1 border-b px-5 py-3.5">
        <p className="kicker text-muted-foreground">Most recent entries</p>
        <p className="kicker text-muted-foreground">newest first</p>
      </div>

      <ol>
        {entries.map((e, i) => (
          <li key={e.entry_hash} className="grid grid-cols-[2.75rem_minmax(0,1fr)] gap-x-3 px-5 py-4 sm:gap-x-5">
            {/* Rail: a node on a continuous spine. Each row draws a full-height
                line, so adjacent rows join into one unbroken thread; the last
                row draws only a stub, leaving the chain open at the bottom
                rather than capped — it continues, we are just showing 50. */}
            <div className="relative flex flex-col items-center">
              <span
                aria-hidden
                className={`absolute left-1/2 top-0 w-px -translate-x-1/2 bg-border ${
                  i === entries.length - 1 ? "h-5" : "h-full"
                }`}
              />
              <span
                aria-hidden
                className="relative mt-1 size-2 rounded-full ring-4 ring-[var(--card)]"
                style={{
                  backgroundColor: e.kind === "original" ? "var(--daylight)" : "var(--tungsten)",
                }}
              />
              <span className="tabular relative mt-2 bg-card px-1 font-mono text-[10px] text-muted-foreground">
                {e.seq}
              </span>
            </div>

            <div className="min-w-0">
              <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
                <span className="text-[13.5px] font-medium tracking-[-0.01em]">{e.kind}</span>
                <span className="font-mono text-[11px] text-muted-foreground">
                  {e.recorded_at}
                </span>
              </div>

              <Link
                href={`/verify/${e.subject_sha256}`}
                className="t-accent mt-1.5 inline-flex min-w-0 items-center gap-1 break-all font-mono text-[12px] underline decoration-1 underline-offset-4 hover:decoration-2"
              >
                <span className="min-w-0">{e.subject_sha256}</span>
                <ArrowUpRight className="size-3 shrink-0" aria-hidden />
              </Link>

              {/* The link itself: what this entry inherited, and what it produced. */}
              <p className="mt-2 flex flex-wrap items-center gap-x-2 gap-y-0.5 font-mono text-[11px] text-muted-foreground">
                <span className="kicker">prev</span>
                <span className="tabular">{short(e.prev_hash)}</span>
                <span aria-hidden>→</span>
                <span className="kicker">this</span>
                <span className="tabular">{short(e.entry_hash)}</span>
              </p>
            </div>
          </li>
        ))}
      </ol>
    </section>
  );
}
