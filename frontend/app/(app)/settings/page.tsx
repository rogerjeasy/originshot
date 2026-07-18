"use client";

import { useEffect, useState } from "react";
import { Check, Loader2, Palette } from "lucide-react";

import { apiFetch } from "@/lib/api";
import { useApiData } from "@/lib/use-api";
import type { BrandKit } from "@/lib/types";
import { CreditsCard } from "@/components/credits-card";
import { FadeIn } from "@/components/motion/fade-in";
import { PageHeader } from "@/components/page-header";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";

const FIELDS: { key: keyof BrandKit; label: string; placeholder: string }[] = [
  { key: "vibe", label: "Vibe", placeholder: "warm, minimal, premium" },
  { key: "lighting", label: "Lighting", placeholder: "soft natural light" },
  { key: "palette", label: "Palette", placeholder: "earthy neutrals" },
  { key: "props", label: "Props", placeholder: "linen, light oak, ceramics" },
];

const EMPTY: BrandKit = { vibe: "", lighting: "", palette: "", props: "", notes: "" };

export default function SettingsPage() {
  const { data, loading } = useApiData<BrandKit>("/api/brand-kit");
  const [form, setForm] = useState<BrandKit>(EMPTY);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Hydrate the form once the saved brand kit loads.
  useEffect(() => {
    if (data) setForm({ ...EMPTY, ...data });
  }, [data]);

  function set(key: keyof BrandKit, value: string) {
    setForm((f) => ({ ...f, [key]: value }));
    setSaved(false);
  }

  async function save(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    setError(null);
    try {
      // Send nulls for blank fields so the backend stores a clean kit.
      const body: BrandKit = Object.fromEntries(
        Object.entries(form).map(([k, v]) => [k, v?.trim() ? v.trim() : null]),
      );
      await apiFetch("/api/brand-kit", { method: "PUT", body: JSON.stringify(body) });
      setSaved(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save");
    } finally {
      setSaving(false);
    }
  }

  // Live preview: compose the filled fields into the phrase the studio will weave in.
  const previewParts = FIELDS.map((f) => form[f.key]?.trim()).filter(Boolean) as string[];

  return (
    <div className="space-y-8">
      <PageHeader
        title="Settings"
        description="Your brand kit guides every generated scene — woven into studio, lifestyle, and variant prompts."
      />

      <div className="grid items-start gap-6 lg:grid-cols-[minmax(0,1fr)_20rem]">
        <FadeIn className="min-w-0">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Palette className="size-4 text-accent" /> Brand kit
              </CardTitle>
            </CardHeader>
            <CardContent>
              {loading ? (
                <div className="space-y-4">
                  {Array.from({ length: 4 }).map((_, i) => (
                    <Skeleton key={i} className="h-10 w-full" />
                  ))}
                  <Skeleton className="h-24 w-full" />
                </div>
              ) : (
                <form onSubmit={save} className="space-y-5">
                  <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                    {FIELDS.map((f) => (
                      <div key={f.key} className="space-y-1.5">
                        <Label htmlFor={f.key}>{f.label}</Label>
                        <Input
                          id={f.key}
                          value={form[f.key] ?? ""}
                          onChange={(e) => set(f.key, e.target.value)}
                          placeholder={f.placeholder}
                        />
                      </div>
                    ))}
                  </div>

                  <div className="space-y-1.5">
                    <Label htmlFor="notes">Notes</Label>
                    <textarea
                      id="notes"
                      value={form.notes ?? ""}
                      onChange={(e) => set("notes", e.target.value)}
                      placeholder="Anything else the studio should know — materials, mood, do's and don'ts."
                      rows={4}
                      maxLength={500}
                      className="flex w-full resize-y rounded-lg border bg-card px-3 py-2 text-sm text-foreground outline-none transition-colors placeholder:text-muted-foreground focus-visible:ring-2 focus-visible:ring-ring"
                    />
                  </div>

                  {error && <Alert>{error}</Alert>}

                  <div className="flex flex-wrap items-center gap-3">
                    <Button type="submit" variant="accent" disabled={saving}>
                      {saving ? <Loader2 className="animate-spin" /> : saved ? <Check /> : null}
                      {saved ? "Saved" : "Save brand kit"}
                    </Button>
                    {saved && (
                      <span className="text-sm text-verified">
                        Applied to your next generation.
                      </span>
                    )}
                  </div>
                </form>
              )}
            </CardContent>
          </Card>
        </FadeIn>

        {/* Credits + live preview — sticky beside the form on lg, stacks below on mobile. */}
        <FadeIn delay={0.08} className="space-y-6 lg:sticky lg:top-20">
          <CreditsCard />

          <Card className="studio-sweep">
            <CardHeader>
              <CardTitle className="text-sm font-medium text-muted-foreground">
                How it reads
              </CardTitle>
            </CardHeader>
            <CardContent>
              {previewParts.length > 0 ? (
                <p className="text-sm leading-relaxed">
                  Every scene rendered with{" "}
                  <span className="font-medium text-accent">{previewParts.join(", ")}</span>
                  {form.notes?.trim() ? (
                    <>
                      {" "}
                      — <span className="text-muted-foreground">{form.notes.trim()}</span>
                    </>
                  ) : (
                    "."
                  )}
                </p>
              ) : (
                <p className="text-sm text-muted-foreground">
                  Fill in your vibe, lighting, palette, and props to preview how the studio will
                  frame every shot.
                </p>
              )}
            </CardContent>
          </Card>
        </FadeIn>
      </div>
    </div>
  );
}
