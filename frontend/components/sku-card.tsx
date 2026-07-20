import Link from "next/link";
import { ArrowUpRight, Check, ImageOff } from "lucide-react";

import type { Sku } from "@/lib/types";
import { RegistrationStrip } from "./workbench/registration";

function formatDate(iso: string): string {
  const d = new Date(iso);
  return Number.isNaN(d.getTime())
    ? ""
    : d.toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" });
}

/**
 * A product in the Studio grid.
 *
 * A SKU is one of the few things in this app that genuinely is a detachable
 * object, so it stays a card rather than becoming a Section. The strip down its
 * leading edge carries the one fact that decides what you can do next: without
 * a source photo there is nothing to generate from.
 *
 * There's no thumbnail here on purpose — Sku carries `original_sha256` but no
 * URL, so showing one would cost a fetch per tile to render decoration.
 */
export function SkuCard({ sku }: { sku: Sku }) {
  const hasPhoto = Boolean(sku.original_sha256);

  return (
    <Link
      href={`/studio/${sku.id}`}
      className="group flex h-full overflow-hidden rounded-lg border bg-card shadow-raised transition-[transform,box-shadow] duration-150 hover:-translate-y-0.5 hover:shadow-float motion-reduce:hover:translate-y-0"
    >
      <RegistrationStrip
        state={hasPhoto ? "verified" : "idle"}
        className="rounded-none"
      />

      <div className="flex min-w-0 flex-1 flex-col gap-3 p-4">
        <div className="flex items-start justify-between gap-2">
          <div className="min-w-0">
            <h3 className="truncate font-semibold tracking-tight">{sku.title}</h3>
            {sku.category && (
              <p className="truncate text-sm text-muted-foreground">{sku.category}</p>
            )}
          </div>
          <ArrowUpRight
            aria-hidden
            className="size-4 shrink-0 text-muted-foreground opacity-0 transition-opacity group-hover:opacity-100"
          />
        </div>

        <div className="mt-auto flex items-center justify-between gap-2 pt-1">
          {/* Colour is never the only channel: the icon and the words carry it too. */}
          <span
            className={`inline-flex items-center gap-1.5 text-xs font-medium ${
              hasPhoto ? "text-verified" : "text-muted-foreground"
            }`}
          >
            {hasPhoto ? <Check className="size-3.5" /> : <ImageOff className="size-3.5" />}
            {hasPhoto ? "Photo ready" : "No photo yet"}
          </span>
          <time className="tabular font-mono text-xs text-muted-foreground">
            {formatDate(sku.created_at)}
          </time>
        </div>
      </div>
    </Link>
  );
}
