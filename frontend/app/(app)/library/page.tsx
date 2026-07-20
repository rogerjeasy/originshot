"use client";

import { useEffect, useMemo, useState } from "react";
import { Images, Search, X } from "lucide-react";

import { cn } from "@/lib/utils";
import { useApiData } from "@/lib/use-api";
import type { Asset, Style } from "@/lib/types";
import { EmptyState } from "@/components/empty-state";
import { FadeIn } from "@/components/motion/fade-in";
import { ImageTile } from "@/components/image-tile";
import { Lightbox } from "@/components/lightbox";
import { PageToolbar } from "@/components/workbench/page-toolbar";
import { Section, Stack } from "@/components/workbench/section";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { MediaSkeleton } from "@/components/ui/skeleton";

/**
 * The Library — everything the seller has stored, across every product.
 *
 * The per-SKU workspace answers "what does this product have?"; this page answers
 * "what do I have?". Filters are server-side (the API call carries them), so what
 * renders is exactly what the query returned — no client-side second opinion that
 * could drift from the API's definition of, say, a QA pass.
 */

const STYLE_FILTERS: { key: "all" | Style; label: string }[] = [
  { key: "all", label: "All styles" },
  { key: "original", label: "Originals" },
  { key: "studio", label: "Studio" },
  { key: "lifestyle", label: "Lifestyle" },
  { key: "onmodel", label: "On model" },
  { key: "variant", label: "Variants" },
  { key: "video", label: "Video" },
];

const SOURCE_FILTERS = [
  { key: "all", label: "Any source" },
  { key: "authentic", label: "Authentic" },
  { key: "ai", label: "AI-generated" },
] as const;

const QA_FILTERS = [
  { key: "all", label: "Any QA" },
  { key: "passed", label: "QA passed" },
  { key: "flagged", label: "QA flagged" },
] as const;

function ChipRow<T extends string>({
  options,
  value,
  onChange,
  label,
}: {
  options: readonly { key: T; label: string }[];
  value: T;
  onChange: (v: T) => void;
  label: string;
}) {
  return (
    <div className="flex flex-wrap gap-2" role="group" aria-label={label}>
      {options.map((o) => {
        const on = value === o.key;
        return (
          <button
            key={o.key}
            type="button"
            aria-pressed={on}
            onClick={() => onChange(o.key)}
            className={cn(
              "rounded-full border px-3 py-1.5 text-sm transition-all active:scale-95",
              on ? "border-transparent bg-accent text-accent-foreground" : "bg-card hover:bg-secondary",
            )}
          >
            {o.label}
          </button>
        );
      })}
    </div>
  );
}

export default function LibraryPage() {
  const [style, setStyle] = useState<"all" | Style>("all");
  const [source, setSource] = useState<(typeof SOURCE_FILTERS)[number]["key"]>("all");
  const [qa, setQa] = useState<(typeof QA_FILTERS)[number]["key"]>("all");
  const [hashInput, setHashInput] = useState("");
  const [hash, setHash] = useState("");
  const [active, setActive] = useState<Asset | null>(null);

  // Debounce the hash box: a query per keystroke would presign the whole page over and
  // over while someone pastes a 64-char hash.
  useEffect(() => {
    const t = setTimeout(() => setHash(hashInput.trim()), 300);
    return () => clearTimeout(t);
  }, [hashInput]);

  const query = useMemo(() => {
    const p = new URLSearchParams();
    if (style !== "all") p.set("style", style);
    if (source !== "all") p.set("authentic", source === "authentic" ? "true" : "false");
    if (qa !== "all") p.set("qa", qa);
    if (hash) p.set("q", hash);
    const s = p.toString();
    return `/api/assets${s ? `?${s}` : ""}`;
  }, [style, source, qa, hash]);

  const { data: assets, loading, error } = useApiData<Asset[]>(query);
  const filtered = style !== "all" || source !== "all" || qa !== "all" || hash !== "";

  function clearFilters() {
    setStyle("all");
    setSource("all");
    setQa("all");
    setHashInput("");
  }

  return (
    <Stack gap="tight">
      <PageToolbar
        title="Library"
        description="Every asset in your catalog — searchable by style, provenance, QA verdict, or content hash."
        meta={
          assets && assets.length > 0 ? (
            <span className="label-mono text-muted-foreground">
              {assets.length} asset{assets.length === 1 ? "" : "s"}
              {filtered ? " matching" : ""}
            </span>
          ) : undefined
        }
      />

      <FadeIn>
        <Section
          label="Filters"
          action={
            filtered ? (
              <Button variant="ghost" size="sm" onClick={clearFilters}>
                <X /> Clear filters
              </Button>
            ) : undefined
          }
        >
          <div className="space-y-4">
            <div className="relative max-w-md">
              <Search className="pointer-events-none absolute start-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
              <Input
                value={hashInput}
                onChange={(e) => setHashInput(e.target.value)}
                placeholder="Search by content hash (sha256 prefix)…"
                className="ps-9 font-mono text-sm"
                aria-label="Search by content hash"
              />
            </div>

            {/* Each row gets a visible legend. The groups were previously
                distinguishable only by their aria-label, so a sighted user had
                to infer that three chip rows meant three independent axes. */}
            <FilterRow legend="Style">
              <ChipRow label="Style" options={STYLE_FILTERS} value={style} onChange={setStyle} />
            </FilterRow>
            <div className="flex flex-wrap gap-x-10 gap-y-4">
              <FilterRow legend="Source">
                <ChipRow label="Source" options={SOURCE_FILTERS} value={source} onChange={setSource} />
              </FilterRow>
              <FilterRow legend="QA verdict">
                <ChipRow label="QA verdict" options={QA_FILTERS} value={qa} onChange={setQa} />
              </FilterRow>
            </div>
          </div>
        </Section>
      </FadeIn>

      {error && <Alert title="Couldn't load your library">{error}</Alert>}

      <Section label={filtered ? "Matching assets" : "All assets"}>
        {loading && !assets ? (
          <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 xl:grid-cols-4">
            {Array.from({ length: 8 }).map((_, i) => (
              <MediaSkeleton key={i} aspect="aspect-square" />
            ))}
          </div>
        ) : !assets || assets.length === 0 ? (
          <EmptyState
            icon={Images}
            title={filtered ? "Nothing matches these filters" : "Nothing in the library yet"}
            description={
              filtered
                ? "Loosen a filter, or clear the hash search."
                : "Upload a product photo in the Studio and generate your first pack."
            }
            action={
              filtered ? (
                <Button variant="outline" size="sm" onClick={clearFilters}>
                  <X /> Clear filters
                </Button>
              ) : undefined
            }
          />
        ) : (
          <FadeIn>
            <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 xl:grid-cols-4">
              {assets.map((a) => (
                <ImageTile key={a.id} asset={a} onClick={() => setActive(a)} />
              ))}
            </div>
          </FadeIn>
        )}
      </Section>

      <Lightbox asset={active} onClose={() => setActive(null)} linkToProduct />
    </Stack>
  );
}

/** A labelled filter axis. The legend is what tells you the rows are independent. */
function FilterRow({ legend, children }: { legend: string; children: React.ReactNode }) {
  return (
    <div className="space-y-1.5">
      <p className="label text-muted-foreground/70">{legend}</p>
      {children}
    </div>
  );
}
