"use client";

import { useState } from "react";
import Link from "next/link";
import { AlertTriangle, Copy, RefreshCw, Search, ShieldCheck, Sparkles } from "lucide-react";

import { apiFetch } from "@/lib/api";
import { useApiData } from "@/lib/use-api";
import type { CatalogIntegrity, CatalogSearchOut, ReindexResult } from "@/lib/types";
import { FadeIn } from "@/components/motion/fade-in";
import { PageToolbar } from "@/components/workbench/page-toolbar";
import { Section } from "@/components/workbench/section";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";

/**
 * Catalog Intelligence — search and integrity over the whole shop.
 *
 * Two questions a growing catalog eventually asks that a per-product view can't:
 * "which of my products match this?" (semantic search) and "is anything in here
 * duplicated or reused?" (integrity). Both read across every SKU the seller owns;
 * the integrity half runs on the pHash + lineage already stored, the search half
 * on embeddings held on B2.
 */
export default function CatalogIntelligencePage() {
  const integrity = useApiData<CatalogIntegrity>("/api/catalog/integrity");

  const [q, setQ] = useState("");
  const [searching, setSearching] = useState(false);
  const [search, setSearch] = useState<CatalogSearchOut | null>(null);
  const [searchError, setSearchError] = useState<string | null>(null);

  const [reindexing, setReindexing] = useState(false);
  const [reindex, setReindex] = useState<ReindexResult | null>(null);

  async function runSearch(e: React.FormEvent) {
    e.preventDefault();
    const query = q.trim();
    if (!query) return;
    setSearching(true);
    setSearchError(null);
    try {
      setSearch(
        await apiFetch<CatalogSearchOut>(`/api/library/search?q=${encodeURIComponent(query)}`),
      );
    } catch (err) {
      setSearchError(err instanceof Error ? err.message : "Search failed");
    } finally {
      setSearching(false);
    }
  }

  async function runReindex() {
    setReindexing(true);
    try {
      const result = await apiFetch<ReindexResult>("/api/catalog/reindex", { method: "POST" });
      setReindex(result);
      if (search) setSearch(null); // stale results after a reindex
    } catch {
      /* surfaced via the reindex result being null */
    } finally {
      setReindexing(false);
    }
  }

  const data = integrity.data;
  const findingCount =
    (data?.reused_originals.length ?? 0) + (data?.near_duplicate_sources.length ?? 0);

  return (
    <>
      <PageToolbar
        title="Catalog Intelligence"
        description="Search your whole catalog by meaning, and surface reused or near-duplicate source photos across products."
      />

      {/* ── Semantic search ─────────────────────────────────────────── */}
      <Section
        label="Search by meaning"
        description="Finds products by what they are, not just by a hash or a filename — over the AI-generated listing text, embedded and stored on B2."
        action={
          <Button variant="secondary" size="sm" onClick={runReindex} disabled={reindexing}>
            <RefreshCw className={reindexing ? "size-4 animate-spin" : "size-4"} />
            {reindexing ? "Indexing…" : "Reindex"}
          </Button>
        }
      >
        <form onSubmit={runSearch} className="flex flex-col gap-2.5 sm:flex-row">
          <div className="relative sm:flex-1">
            <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
            <Input
              value={q}
              onChange={(e) => setQ(e.target.value)}
              placeholder="e.g. handmade ceramic, natural linen, minimalist packaging"
              className="pl-9"
              disabled={searching}
            />
          </div>
          <Button type="submit" variant="accent" className="sm:shrink-0" disabled={searching}>
            <Sparkles className="size-4" />
            Search
          </Button>
        </form>

        {reindex && (
          <p className="mt-3 text-[13px] text-muted-foreground">
            {reindex.available
              ? `Indexed ${reindex.embedded} product${reindex.embedded === 1 ? "" : "s"} (${reindex.skipped} unchanged/skipped of ${reindex.total}).`
              : "Semantic search is off on this instance (no OpenAI key configured). Visual and integrity checks below still work."}
          </p>
        )}
        {searchError && (
          <div className="mt-4">
            <Alert title="Couldn't search">{searchError}</Alert>
          </div>
        )}
        {search && (
          <div className="mt-4">
            {!search.available ? (
              <Alert title="Semantic search isn't configured">
                It needs an OpenAI key on this instance. The integrity checks below don&apos;t —
                they run on data already stored.
              </Alert>
            ) : search.hits.length === 0 ? (
              <p className="text-sm text-muted-foreground">
                No products matched
                {search.indexed === 0
                  ? " — nothing is indexed yet. Run a reindex, then try again."
                  : `. ${search.indexed} product${search.indexed === 1 ? "" : "s"} indexed.`}
              </p>
            ) : (
              <ul className="divide-y overflow-hidden rounded-xl border bg-card">
                {search.hits.map((hit) => (
                  <li key={hit.sku_id}>
                    <Link
                      href={`/studio/${hit.sku_id}`}
                      className="flex items-center gap-4 p-4 transition-colors hover:bg-secondary"
                    >
                      <span className="min-w-0 flex-1">
                        <span className="block truncate text-[14.5px] font-medium">
                          {hit.title || "Untitled product"}
                        </span>
                        {hit.category && (
                          <span className="block truncate text-[13px] text-muted-foreground">
                            {hit.category}
                          </span>
                        )}
                      </span>
                      <span className="flex items-center gap-2">
                        <span
                          className="h-1.5 w-20 overflow-hidden rounded-full bg-muted"
                          aria-hidden
                        >
                          <span
                            className="block h-full rounded-full bg-accent"
                            style={{ width: `${Math.round(Math.min(1, hit.score) * 100)}%` }}
                          />
                        </span>
                        <span className="tabular w-10 text-right font-mono text-xs text-muted-foreground">
                          {hit.score.toFixed(2)}
                        </span>
                      </span>
                    </Link>
                  </li>
                ))}
              </ul>
            )}
          </div>
        )}
      </Section>

      {/* ── Integrity ───────────────────────────────────────────────── */}
      <Section
        label="Catalog integrity"
        description="Signals for review, never accusations: one authentic photo behind several listings, or near-identical source uploads across products."
      >
        {integrity.loading ? (
          <Skeleton className="h-24 w-full" />
        ) : integrity.error ? (
          <Alert title="Couldn't load integrity">{integrity.error}</Alert>
        ) : findingCount === 0 ? (
          <div className="flex items-center gap-3 rounded-xl border bg-card p-5">
            <ShieldCheck className="size-5 shrink-0 text-verified" aria-hidden />
            <p className="text-[14.5px]">
              No reused or near-duplicate source photos across your{" "}
              {data?.skus_analyzed ?? 0} product{data?.skus_analyzed === 1 ? "" : "s"}.
            </p>
          </div>
        ) : (
          <div className="space-y-6">
            {data!.reused_originals.length > 0 && (
              <IntegrityGroup
                icon={<Copy className="size-4 text-warning" aria-hidden />}
                title="Same authentic photo, multiple listings"
                blurb="One pre-AI original is the source for more than one product. Legitimate for true variants — worth a look otherwise."
              >
                {data!.reused_originals.map((f) => (
                  <FindingRow
                    key={f.parent_sha256}
                    heading={
                      <>
                        original{" "}
                        <code className="font-mono text-[12px]">
                          {f.parent_sha256.slice(0, 12)}…
                        </code>{" "}
                        → {f.sku_count} products
                      </>
                    }
                    skuIds={f.sku_ids}
                  />
                ))}
              </IntegrityGroup>
            )}

            {data!.near_duplicate_sources.length > 0 && (
              <IntegrityGroup
                icon={<AlertTriangle className="size-4 text-warning" aria-hidden />}
                title="Near-identical source photos across products"
                blurb="Different uploads that look like the same picture (a re-save or a re-shoot of one item) — pHash caught them even though the bytes differ."
              >
                {data!.near_duplicate_sources.map((f, i) => (
                  <FindingRow
                    key={i}
                    heading={<>{f.sku_count} products share a near-identical source</>}
                    skuIds={f.sku_ids}
                  />
                ))}
              </IntegrityGroup>
            )}
          </div>
        )}
      </Section>
    </>
  );
}

function IntegrityGroup({
  icon,
  title,
  blurb,
  children,
}: {
  icon: React.ReactNode;
  title: string;
  blurb: string;
  children: React.ReactNode;
}) {
  return (
    <FadeIn className="overflow-hidden rounded-xl border bg-card">
      <div className="border-b bg-muted/40 px-5 py-3.5">
        <p className="flex items-center gap-2 text-[14px] font-medium">
          {icon}
          {title}
        </p>
        <p className="mt-1 text-[13px] leading-relaxed text-muted-foreground">{blurb}</p>
      </div>
      <ul className="divide-y">{children}</ul>
    </FadeIn>
  );
}

function FindingRow({ heading, skuIds }: { heading: React.ReactNode; skuIds: string[] }) {
  return (
    <li className="px-5 py-4">
      <p className="text-[14px]">{heading}</p>
      <div className="mt-2 flex flex-wrap gap-2">
        {skuIds.map((id) => (
          <Link
            key={id}
            href={`/studio/${id}`}
            className="rounded border bg-secondary px-2 py-1 font-mono text-[11px] text-muted-foreground transition-colors hover:text-foreground"
          >
            {id.slice(0, 8)}
          </Link>
        ))}
      </div>
    </li>
  );
}
