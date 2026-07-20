import Link from "next/link";
import { ArrowUpRight, Check, ImageOff } from "lucide-react";

import type { Sku } from "@/lib/types";
import { RegistrationStrip } from "./workbench/registration";
import { SkuSettings } from "./studio/sku-settings";

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
 * Edit/delete controls overlay the top-right on hover or keyboard focus. They are
 * siblings of the navigational link, not children of it, so a click on them never
 * triggers the card's own navigation and no interactive element is nested in an anchor.
 */
export function SkuCard({ sku, onChanged }: { sku: Sku; onChanged?: () => void }) {
  const hasPhoto = Boolean(sku.original_sha256);

  return (
    <div className="group relative h-full">
      <Link
        href={`/studio/${sku.id}`}
        className="flex h-full overflow-hidden rounded-lg border bg-card shadow-raised transition-[transform,box-shadow] duration-150 hover:-translate-y-0.5 hover:shadow-float motion-reduce:hover:translate-y-0"
      >
        <RegistrationStrip state={hasPhoto ? "verified" : "idle"} className="rounded-none" />

        <div className="flex min-w-0 flex-1 flex-col gap-3 p-4">
          <div className="flex items-start justify-between gap-2">
            <div className="min-w-0">
              {/* Right padding leaves room for the hover action cluster so a long title
                  never slides under the icons. */}
              <h3 className="truncate pe-16 font-semibold tracking-tight">{sku.title}</h3>
              {sku.category && (
                <p className="truncate text-sm text-muted-foreground">{sku.category}</p>
              )}
            </div>
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

      {/* At rest a subtle arrow signals the card is navigable; on hover (or when a control
          inside gains keyboard focus) it gives way to the edit/delete cluster. */}
      <div className="absolute end-3 top-3 flex items-center">
        <ArrowUpRight
          aria-hidden
          className="pointer-events-none size-4 text-muted-foreground opacity-50 transition-opacity group-hover:opacity-0 group-focus-within:opacity-0"
        />
        <div className="absolute end-0 top-0 opacity-0 transition-opacity group-hover:opacity-100 focus-within:opacity-100">
          <SkuSettings sku={sku} layout="icons" onSaved={onChanged} onDeleted={onChanged} />
        </div>
      </div>
    </div>
  );
}
