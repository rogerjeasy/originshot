import { Card, CardContent } from "@/components/ui/card";

export function TypeScale() {
  return (
    <Card>
      <CardContent className="space-y-3 pt-5">
        <p className="text-3xl font-semibold tracking-tight">Geist Sans · display</p>
        <p className="text-base text-muted-foreground">
          Body copy in Geist Sans at 16px / 1.55 — calm, legible scaffolding so the photos are the
          loudest thing on screen.
        </p>
        <p className="font-mono text-sm">
          Geist Mono · sha256 7f3a…b1c4 · SKU-00421 · 2048×2048 · $0.04
        </p>
      </CardContent>
    </Card>
  );
}
