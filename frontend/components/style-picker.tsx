"use client";

import { Sparkles } from "lucide-react";

import { cn } from "@/lib/utils";
import type { Style } from "@/lib/types";

const OPTIONS: { key: Style; label: string }[] = [
  { key: "studio", label: "Studio" },
  { key: "lifestyle", label: "Lifestyle" },
  { key: "onmodel", label: "On-model" },
  { key: "variant", label: "Variants" },
  { key: "video", label: "Video" },
  { key: "voiceover", label: "Voiceover" },
];

export function StylePicker({
  value,
  onChange,
}: {
  value: Style[];
  onChange: (styles: Style[]) => void;
}) {
  function toggle(s: Style) {
    onChange(value.includes(s) ? value.filter((x) => x !== s) : [...value, s]);
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
              "inline-flex items-center gap-1.5 rounded-full border px-3 py-1.5 text-sm transition-all active:scale-95",
              on
                ? "border-transparent bg-accent text-accent-foreground"
                : "bg-card hover:bg-secondary",
            )}
          >
            {on && <Sparkles className="size-3.5" />}
            {o.label}
          </button>
        );
      })}
    </div>
  );
}
