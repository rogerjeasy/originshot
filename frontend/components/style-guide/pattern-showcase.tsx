import { Image as ImageIcon, Sparkles } from "lucide-react";

import { ProvenanceBadge } from "@/components/provenance-badge";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

const STYLES = ["Studio", "Lifestyle", "On-model", "Variants", "Video"];

/** Composite OriginShot patterns (framed tile, stat card, style pills) for reference. */
export function PatternShowcase() {
  return (
    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
      {/* Framed image tile */}
      <Card className="overflow-hidden">
        <div className="studio-sweep frame relative grid aspect-square place-items-center border-b">
          <ImageIcon className="size-10 text-muted-foreground" />
          <div className="absolute bottom-3 start-3">
            <ProvenanceBadge authentic={false} sha="9d8c7b6a5e4f3d2c1b0a99887766" />
          </div>
        </div>
        <CardHeader>
          <CardTitle className="truncate">Ceramic Mug — studio</CardTitle>
          <p className="font-mono text-xs text-muted-foreground">1:1 · 2048×2048 · png</p>
        </CardHeader>
      </Card>

      {/* Stat card (sample values — illustrates the mono/tabular treatment) */}
      <Card>
        <CardHeader>
          <CardTitle className="text-sm font-medium text-muted-foreground">
            Assets generated
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="tabular text-4xl font-semibold tracking-tight">1,284</div>
          <p className="mt-1 text-sm text-verified">↑ 38% dedup savings on B2</p>
        </CardContent>
      </Card>

      {/* Style pills */}
      <Card>
        <CardHeader>
          <CardTitle className="text-sm font-medium text-muted-foreground">Output styles</CardTitle>
        </CardHeader>
        <CardContent className="flex flex-wrap gap-2">
          {STYLES.map((s, i) => (
            <Badge key={s} variant={i === 0 ? "accent" : "secondary"}>
              {i === 0 ? <Sparkles /> : null}
              {s}
            </Badge>
          ))}
        </CardContent>
      </Card>
    </div>
  );
}
