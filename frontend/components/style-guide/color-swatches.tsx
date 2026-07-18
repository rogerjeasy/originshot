/**
 * Colour reference. Each swatch names the ColorChecker patch it derives from,
 * because that provenance is the argument for the palette — see
 * docs/DESIGN_SYSTEM.md.
 */
const SEMANTIC = [
  { name: "background", token: "--color-background", note: "below patch 19" },
  { name: "card", token: "--color-card", note: "—" },
  { name: "primary", token: "--color-primary", note: "studio ink" },
  { name: "muted", token: "--color-muted", note: "greyscale ramp" },
  { name: "accent", token: "--color-accent", note: "patch 13 · blue" },
  { name: "verified", token: "--color-verified", note: "patch 14 · green" },
  { name: "warning", token: "--color-warning", note: "patch 7 · orange" },
  { name: "danger", token: "--color-danger", note: "patch 15 · red" },
];

const CHART = [
  { name: "chart-1", token: "--color-chart-1", note: "patch 7, re-stepped" },
  { name: "chart-2", token: "--color-chart-2", note: "patch 13, re-stepped" },
  { name: "chart-3", token: "--color-chart-3", note: "patch 14, re-stepped" },
  { name: "chart-4", token: "--color-chart-4", note: "patch 17, re-stepped" },
];

function Swatch({ name, token, note }: { name: string; token: string; note: string }) {
  return (
    <div className="min-w-0">
      <div
        className="frame mb-2 aspect-[4/3] w-full rounded-md border"
        style={{ backgroundColor: `var(${token})` }}
      />
      <div className="truncate text-sm font-medium">{name}</div>
      <div className="truncate font-mono text-[11px] text-muted-foreground">{token}</div>
      <div className="truncate text-[11px] text-muted-foreground/80">{note}</div>
    </div>
  );
}

export function ColorSwatches() {
  return (
    <div className="space-y-8">
      <div>
        <p className="label mb-3 text-muted-foreground">Semantic</p>
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-4 lg:grid-cols-8">
          {SEMANTIC.map((s) => (
            <Swatch key={s.name} {...s} />
          ))}
        </div>
      </div>

      <div>
        <p className="label mb-1 text-muted-foreground">Categorical chart ramp</p>
        <p className="mb-3 max-w-2xl text-sm text-muted-foreground">
          Four slots, assigned in fixed order and never cycled. The raw patches failed
          validation as a data palette — too dark, too low-chroma, and cyan/purple were
          indistinguishable under protanopia — so these are re-stepped until every check
          passes in both light and dark.
        </p>
        {/* Same track as the semantic row above, so a four-slot ramp doesn't
            render at twice the size of an eight-slot one. */}
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-4 lg:grid-cols-8">
          {CHART.map((s) => (
            <Swatch key={s.name} {...s} />
          ))}
        </div>
      </div>
    </div>
  );
}
