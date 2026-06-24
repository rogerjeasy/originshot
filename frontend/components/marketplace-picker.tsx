"use client";

import { cn } from "@/lib/utils";
import type { Marketplace } from "@/lib/types";

const OPTIONS: { key: Marketplace; label: string }[] = [
  { key: "amazon", label: "Amazon" },
  { key: "etsy", label: "Etsy" },
  { key: "shopify", label: "Shopify" },
  { key: "ebay", label: "eBay" },
  { key: "social", label: "Social" },
];

/** Marketplace preset selector — drives studio aspect + export format targets. */
export function MarketplacePicker({
  value,
  onChange,
}: {
  value: Marketplace[];
  onChange: (next: Marketplace[]) => void;
}) {
  function toggle(m: Marketplace) {
    onChange(value.includes(m) ? value.filter((x) => x !== m) : [...value, m]);
  }

  return (
    <div className="flex flex-wrap gap-2">
      {OPTIONS.map((o) => {
        const on = value.includes(o.key);
        return (
          <button
            key={o.key}
            type="button"
            aria-pressed={on}
            onClick={() => toggle(o.key)}
            className={cn(
              "inline-flex items-center rounded-full border px-3 py-1.5 text-sm transition-all active:scale-95",
              on ? "border-transparent bg-primary text-primary-foreground" : "bg-card hover:bg-secondary",
            )}
          >
            {o.label}
          </button>
        );
      })}
    </div>
  );
}
