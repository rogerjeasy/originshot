import { Terminal } from "lucide-react";

/**
 * The only real evidence on the page, styled to outrank everything else on it.
 *
 * Everything above is rendered by the same server that wrote the log, so none of
 * it proves anything on its own. This block is the one thing that does, so it
 * has to outrank the panels around it.
 *
 * On the ink ground it can't do that by inverting — the page is already dark, and
 * in dark theme --ink-2 and --card are within a few points of each other. So it
 * is marked with a tungsten hairline instead: the action colour, used as a
 * stroke, which is the one thing on the page drawn in it. That reads in both
 * themes and on either ground.
 *
 * The closing paragraph states what this still can't prove. That is not hedging
 * — a single-operator log genuinely cannot rule out showing a different chain to
 * a different reader, and a transparency page that omitted it would be doing the
 * exact thing the feature exists to prevent.
 */
const LINES = [
  { cmd: "python scripts/verify_ledger.py --save checkpoint.json" },
  { note: "# ...later..." },
  { cmd: "python scripts/verify_ledger.py --against checkpoint.json" },
];

export function VerifyYourself() {
  return (
    <section
      className="band-ink overflow-hidden rounded-xl border"
      style={{ borderColor: "var(--tungsten)" }}
    >
      <div className="p-6 sm:p-7">
        <p className="kicker t-accent inline-flex items-center gap-2">
          <Terminal className="size-3.5" aria-hidden />
          Independent verification
        </p>
        <h2 className="display-face mt-3 text-[1.75rem]">Don&apos;t take our word for it.</h2>
        <p className="on-ink-mute mt-3 max-w-2xl text-[14.5px] leading-relaxed">
          This page is rendered by the same server that wrote the log, so it proves nothing on its
          own. The verifier talks only to the public endpoints and recomputes every hash locally.
        </p>

        <pre
          className="scroll-thin mt-6 overflow-x-auto rounded-lg border p-4 font-mono text-[12.5px] leading-relaxed"
          style={{ backgroundColor: "var(--ink)" }}
        >
          {LINES.map((l, i) =>
            l.cmd ? (
              <div key={i}>
                <span className="t-verify select-none" aria-hidden>
                  ${" "}
                </span>
                {l.cmd}
              </div>
            ) : (
              <div key={i} className="on-ink-mute">
                {l.note}
              </div>
            ),
          )}
        </pre>

        <p className="on-ink-mute mt-5 max-w-2xl text-[13.5px] leading-relaxed">
          Saving a checkpoint and re-checking later is the strongest guarantee available here: it
          proves the log only ever grew. It is not signed, and a single-operator log can&apos;t rule
          out showing a different chain to someone else — that needs independent witnesses, which
          we don&apos;t have.
        </p>
      </div>
    </section>
  );
}
