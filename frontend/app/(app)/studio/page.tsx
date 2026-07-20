"use client";

import { useState } from "react";
import Link from "next/link";
import { ArrowRight, Layers, Loader2, Package, Plus } from "lucide-react";

import { apiFetch } from "@/lib/api";
import { useApiData } from "@/lib/use-api";
import type { Sku } from "@/lib/types";
import { EmptyState } from "@/components/empty-state";
import { FadeIn } from "@/components/motion/fade-in";
import { Stagger, StaggerItem } from "@/components/motion/stagger";
import { SkuCard } from "@/components/sku-card";
import { PageToolbar } from "@/components/workbench/page-toolbar";
import { Section, Stack } from "@/components/workbench/section";
import { Alert } from "@/components/ui/alert";
import { Button, buttonVariants } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";

export default function StudioPage() {
  const { data: skus, loading, reload } = useApiData<Sku[]>("/api/skus");
  const [title, setTitle] = useState("");
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function create(e: React.FormEvent) {
    e.preventDefault();
    if (!title.trim()) return;
    setCreating(true);
    setError(null);
    try {
      await apiFetch("/api/skus", { method: "POST", body: JSON.stringify({ title }) });
      setTitle("");
      await reload();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create");
    } finally {
      setCreating(false);
    }
  }

  const count = skus?.length ?? 0;

  return (
    <Stack>
      <PageToolbar
        title="Studio"
        description="Create a product, then turn one photo into a full pack."
        action={
          <Link href="/studio/catalog" className={buttonVariants({ variant: "outline" })}>
            <Layers /> Catalog Mode
          </Link>
        }
        meta={
          count > 0 ? (
            <span className="label-mono text-muted-foreground">
              {count} product{count === 1 ? "" : "s"}
            </span>
          ) : undefined
        }
      />

      <FadeIn>
        <Section label="New product" state={creating ? "working" : undefined}>
          <form onSubmit={create} className="flex flex-col gap-3 sm:flex-row">
            <Input
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="e.g. Handmade ceramic mug"
              className="sm:flex-1"
              aria-label="Product title"
            />
            <Button type="submit" variant="accent" disabled={creating || !title.trim()}>
              {creating ? <Loader2 className="animate-spin" /> : <Plus />} Create product
            </Button>
          </form>
          {error && (
            <Alert className="mt-3" title="Couldn't create that product">
              {error}
            </Alert>
          )}

          {/* The single-product form above is the right default; a shop with a
              hundred SKUs needs to know the other door exists before they use
              this one a hundred times. */}
          <Link
            href="/studio/catalog"
            className="group mt-4 flex items-start gap-3 rounded-md border border-dashed p-3.5 transition-colors hover:border-solid hover:bg-secondary"
          >
            <Layers className="mt-0.5 size-4 shrink-0 t-accent" />
            <span className="min-w-0 flex-1">
              <span className="block text-sm font-medium">Got a whole shop to photograph?</span>
              <span className="mt-0.5 block text-sm text-muted-foreground">
                Catalog Mode takes a folder of photos and generates every product in one run,
                with a live board and a single download at the end.
              </span>
            </span>
            <ArrowRight
              aria-hidden
              className="mt-0.5 size-4 shrink-0 text-muted-foreground transition-transform group-hover:translate-x-0.5 motion-reduce:group-hover:translate-x-0"
            />
          </Link>
        </Section>
      </FadeIn>

      <Section label="Products">
        {loading ? (
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {Array.from({ length: 3 }).map((_, i) => (
              <Skeleton key={i} className="h-[7.5rem]" />
            ))}
          </div>
        ) : !skus?.length ? (
          <EmptyState
            icon={Package}
            title="No products yet"
            description="Name a product above and it appears here, ready for its source photo."
          />
        ) : (
          <Stagger className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {skus.map((s) => (
              <StaggerItem key={s.id}>
                <SkuCard sku={s} />
              </StaggerItem>
            ))}
          </Stagger>
        )}
      </Section>
    </Stack>
  );
}
