"use client";

import { useState } from "react";
import { Loader2, Package, Plus } from "lucide-react";

import { apiFetch } from "@/lib/api";
import { useApiData } from "@/lib/use-api";
import type { Sku } from "@/lib/types";
import { EmptyState } from "@/components/empty-state";
import { FadeIn } from "@/components/motion/fade-in";
import { Stagger, StaggerItem } from "@/components/motion/stagger";
import { PageHeader } from "@/components/page-header";
import { SkuCard } from "@/components/sku-card";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
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
    <div className="space-y-8">
      <PageHeader
        title="Studio"
        description="Create a product, then turn one photo into a full pack."
        action={
          count > 0 ? (
            <span className="tabular rounded-full border bg-card px-3 py-1.5 text-sm text-muted-foreground">
              {count} product{count === 1 ? "" : "s"}
            </span>
          ) : null
        }
      />

      <FadeIn>
        <Card className="studio-sweep">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Plus className="size-4 text-accent" /> New product
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <form onSubmit={create} className="flex flex-col gap-3 sm:flex-row">
              <Input
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                placeholder="e.g. Handmade ceramic mug"
                className="sm:flex-1"
                aria-label="Product title"
              />
              <Button type="submit" variant="accent" disabled={creating || !title.trim()}>
                {creating ? <Loader2 className="animate-spin" /> : <Plus />} Create
              </Button>
            </form>
            {error && <Alert>{error}</Alert>}
          </CardContent>
        </Card>
      </FadeIn>

      {loading ? (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {Array.from({ length: 3 }).map((_, i) => (
            <Skeleton key={i} className="h-32" />
          ))}
        </div>
      ) : !skus?.length ? (
        <EmptyState
          icon={Package}
          title="No products yet"
          description="Create your first product above to start a studio pack."
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
    </div>
  );
}
