const SWATCHES = [
  { name: "background", token: "--color-background" },
  { name: "card", token: "--color-card" },
  { name: "primary", token: "--color-primary" },
  { name: "accent", token: "--color-accent" },
  { name: "verified", token: "--color-verified" },
  { name: "muted", token: "--color-muted" },
  { name: "warning", token: "--color-warning" },
  { name: "danger", token: "--color-danger" },
];

export function ColorSwatches() {
  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-4 lg:grid-cols-8">
      {SWATCHES.map((s) => (
        <div key={s.name} className="min-w-0">
          <div
            className="frame mb-2 aspect-[4/3] w-full rounded-lg border"
            style={{ backgroundColor: `var(${s.token})` }}
          />
          <div className="truncate text-sm font-medium">{s.name}</div>
          <div className="truncate font-mono text-xs text-muted-foreground">{s.token}</div>
        </div>
      ))}
    </div>
  );
}
