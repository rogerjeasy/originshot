import { cn } from "@/lib/utils";
import { CountUp } from "./motion/count-up";
import { Lattice } from "./workbench/section";

/**
 * A metric, not a card-in-a-card.
 *
 * These sit in a bordered grid where the cell divisions do the framing, so each
 * tile is just a label and a figure. Numbers are mono and tabular so a column
 * of them lines up on the decimal. Values must come from real data — never a
 * placeholder figure.
 */
export function StatCard({
  label,
  value,
  decimals = 0,
  prefix = "",
  suffix = "",
  tone = "default",
  hint,
  className,
}: {
  label: string;
  value: number;
  decimals?: number;
  prefix?: string;
  suffix?: string;
  /** `verified` for figures that are good news (savings); keep it rare. */
  tone?: "default" | "verified" | "warning";
  hint?: string;
  className?: string;
}) {
  return (
    <div className={cn("flex flex-col gap-1 bg-card p-5", className)}>
      <p className="label text-muted-foreground">{label}</p>
      <p
        className={cn(
          "tabular font-mono text-[28px] font-medium leading-none tracking-tight",
          tone === "verified" && "text-verified",
          tone === "warning" && "text-warning",
        )}
      >
        <CountUp value={value} decimals={decimals} prefix={prefix} suffix={suffix} />
      </p>
      {hint && <p className="mt-0.5 text-xs text-muted-foreground">{hint}</p>}
    </div>
  );
}

/**
 * The grid these live in: hairline divisions, no nested card borders.
 *
 * This was the original home of that pattern; it's now Lattice, which the rest
 * of the app uses for any set of peer cells. StatGrid stays as the named
 * four-column case so metric callers keep reading as metrics.
 */
export function StatGrid({ className, children }: { className?: string; children: React.ReactNode }) {
  return (
    <Lattice columns={4} className={className}>
      {children}
    </Lattice>
  );
}
