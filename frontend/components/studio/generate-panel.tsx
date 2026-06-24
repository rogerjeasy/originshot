import { Download, Loader2, Wand2 } from "lucide-react";

import type { Job, Marketplace, Style } from "@/lib/types";
import { MarketplacePicker } from "@/components/marketplace-picker";
import { StylePicker } from "@/components/style-picker";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="space-y-2">
      <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">{label}</p>
      {children}
    </div>
  );
}

/** Generation controls: style + marketplace pickers, generate/export actions, job status. */
export function GeneratePanel({
  styles,
  onStylesChange,
  marketplaces,
  onMarketplacesChange,
  hasOriginal,
  busy,
  onGenerate,
  canExport,
  onExport,
  job,
}: {
  styles: Style[];
  onStylesChange: (s: Style[]) => void;
  marketplaces: Marketplace[];
  onMarketplacesChange: (m: Marketplace[]) => void;
  hasOriginal: boolean;
  busy: boolean;
  onGenerate: () => void;
  canExport: boolean;
  onExport: () => void;
  job: Job | null;
}) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Generate</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <Field label="Styles">
          <StylePicker value={styles} onChange={onStylesChange} />
        </Field>
        <Field label="Marketplaces">
          <MarketplacePicker value={marketplaces} onChange={onMarketplacesChange} />
        </Field>

        <Button
          variant="accent"
          className="w-full"
          disabled={!hasOriginal || styles.length === 0 || busy}
          onClick={onGenerate}
        >
          {busy ? <Loader2 className="animate-spin" /> : <Wand2 />}
          {busy ? "Generating…" : "Generate pack"}
        </Button>

        {!hasOriginal && <p className="text-xs text-muted-foreground">Upload a photo first.</p>}
        {job?.status === "done" && typeof job.cost_estimate === "number" && (
          <p className="font-mono text-xs text-muted-foreground">
            est. cost ${job.cost_estimate.toFixed(2)}
          </p>
        )}
        {job?.status === "partial" && (
          <p className="text-xs text-warning">
            Some styles fell back or failed — partial pack delivered.
          </p>
        )}

        <Button variant="outline" className="w-full" disabled={!canExport} onClick={onExport}>
          <Download /> Export pack
        </Button>
      </CardContent>
    </Card>
  );
}
