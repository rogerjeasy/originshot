import { ProviderChart } from "@/components/provider-chart";
import { StatCard, StatGrid } from "@/components/stat-card";

/**
 * The data-display pieces the Analytics and Admin dashboards are built from.
 * Kept on the public style guide so the figures behind auth can still be
 * eyeballed — these are illustrative values, not live ones.
 */
export function DataDisplay() {
  return (
    <div className="space-y-8">
      <div>
        <p className="label mb-3 text-muted-foreground">Stat grid</p>
        <StatGrid>
          <StatCard label="Total assets" value={1284} />
          <StatCard label="Unique objects" value={903} hint="distinct content hashes" />
          <StatCard
            label="Storage saved"
            value={29.7}
            decimals={1}
            suffix="%"
            tone="verified"
            hint="duplicate bytes never written"
          />
          <StatCard
            label="Fallback rate"
            value={12.4}
            decimals={1}
            suffix="%"
            tone="warning"
            hint="primary model failed, fallback succeeded"
          />
        </StatGrid>
      </div>

      <div className="max-w-xl">
        <p className="label mb-1 text-muted-foreground">Provider mix</p>
        <p className="mb-4 text-sm text-muted-foreground">
          One series, so one hue — colour would only restate the row label. Values are
          direct-labelled, so no bar has to be measured against a gridline.
        </p>
        <div className="rounded-lg border bg-card p-5">
          <ProviderChart data={{ genblaze: 812, "openai-fallback": 71, local: 20 }} />
        </div>
      </div>
    </div>
  );
}
