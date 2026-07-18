import Link from "next/link";
import { Check, ImageOff } from "lucide-react";

import type { Sku } from "@/lib/types";
import { Card, CardContent, CardHeader, CardHeading } from "./ui/card";

function formatDate(iso: string): string {
  const d = new Date(iso);
  return Number.isNaN(d.getTime())
    ? ""
    : d.toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" });
}

/** Product summary tile for the Studio grid. */
export function SkuCard({ sku }: { sku: Sku }) {
  const hasPhoto = Boolean(sku.original_sha256);
  return (
    <Link href={`/studio/${sku.id}`} className="block h-full">
      <Card className="lift h-full">
        <CardHeader>
          <CardHeading className="truncate">{sku.title}</CardHeading>
          {sku.category && (
            <p className="truncate text-sm text-muted-foreground">{sku.category}</p>
          )}
        </CardHeader>
        <CardContent className="flex items-center justify-between gap-2">
          <span
            className="inline-flex items-center gap-1.5 text-xs font-medium"
            style={{ color: hasPhoto ? "var(--color-verified)" : "var(--color-muted-foreground)" }}
          >
            {hasPhoto ? <Check className="size-3.5" /> : <ImageOff className="size-3.5" />}
            {hasPhoto ? "Photo ready" : "No photo yet"}
          </span>
          <time className="font-mono text-xs text-muted-foreground">
            {formatDate(sku.created_at)}
          </time>
        </CardContent>
      </Card>
    </Link>
  );
}
