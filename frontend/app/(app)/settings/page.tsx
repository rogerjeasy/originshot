"use client";

import { useEffect, useMemo, useState } from "react";
import { Check, Loader2 } from "lucide-react";

import { apiFetch } from "@/lib/api";
import { useApiData } from "@/lib/use-api";
import type { BrandKit } from "@/lib/types";
import { AccountPanel } from "@/components/account-panel";
import { CreditsCard } from "@/components/credits-card";
import { FadeIn } from "@/components/motion/fade-in";
import { PageHeader } from "@/components/page-header";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input, Textarea } from "@/components/ui/input";
import { Field } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";

const FIELDS: { key: keyof BrandKit; label: string; placeholder: string; hint: string }[] = [
  {
    key: "vibe",
    label: "Vibe",
    placeholder: "warm, minimal, premium",
    hint: "The overall feel of a scene",
  },
  {
    key: "lighting",
    label: "Lighting",
    placeholder: "soft natural light",
    hint: "How the product is lit",
  },
  {
    key: "palette",
    label: "Palette",
    placeholder: "earthy neutrals",
    hint: "Colours that surround the product",
  },
  {
    key: "props",
    label: "Props",
    placeholder: "linen, light oak, ceramics",
    hint: "What can share the frame",
  },
];

const NOTES_MAX = 500;
const EMPTY: BrandKit = { vibe: "", lighting: "", palette: "", props: "", notes: "" };

/** Blank strings and nulls mean the same thing here; compare them that way. */
function normalize(kit: BrandKit): string {
  return JSON.stringify(
    Object.fromEntries(
      Object.entries({ ...EMPTY, ...kit }).map(([k, v]) => [k, (v ?? "").trim()]),
    ),
  );
}

export default function SettingsPage() {
  const { data, loading, setData } = useApiData<BrandKit>("/api/brand-kit");
  const [form, setForm] = useState<BrandKit>(EMPTY);
  const [saving, setSaving] = useState(false);
  const [justSaved, setJustSaved] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Hydrate the form once the saved brand kit loads.
  useEffect(() => {
    if (data) setForm({ ...EMPTY, ...data });
  }, [data]);

  const dirty = useMemo(
    () => (data ? normalize(form) !== normalize(data) : false),
    [form, data],
  );

  function set(key: keyof BrandKit, value: string) {
    setForm((f) => ({ ...f, [key]: value }));
    setJustSaved(false);
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
      // Re-baseline locally so the form stops reading as dirty without a refetch.
      setData(body);
      setJustSaved(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Couldn't save your brand kit");
    } finally {
      setSaving(false);
    }
  }

  // Live preview: compose the filled fields into the phrase the studio weaves in.
  const previewParts = FIELDS.map((f) => form[f.key]?.trim()).filter(Boolean) as string[];
  const notes = form.notes ?? "";

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
              <CardTitle>Brand kit</CardTitle>
              <CardDescription>
                Leave anything blank and the studio makes its own choice for that part.
              </CardDescription>
            </CardHeader>

            {loading ? (
              <CardContent className="space-y-4">
                <div className="grid gap-4 sm:grid-cols-2">
                  {Array.from({ length: 4 }).map((_, i) => (
                    <Skeleton key={i} className="h-16 w-full" />
                  ))}
                </div>
                <Skeleton className="h-28 w-full" />
              </CardContent>
            ) : (
              <form onSubmit={save}>
                <CardContent className="space-y-5">
                  <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                    {FIELDS.map((f) => (
                      <Field key={f.key} htmlFor={f.key} label={f.label} hint={f.hint}>
                        <Input
                          value={form[f.key] ?? ""}
                          onChange={(e) => set(f.key, e.target.value)}
                          placeholder={f.placeholder}
                        />
                      </Field>
                    ))}
                  </div>

                  <Field
                    htmlFor="notes"
                    label="Notes"
                    hint={`${notes.length} of ${NOTES_MAX} characters`}
                  >
                    <Textarea
                      value={notes}
                      onChange={(e) => set("notes", e.target.value.slice(0, NOTES_MAX))}
                      placeholder="Anything else the studio should know — materials, mood, things to avoid."
                      rows={4}
                      maxLength={NOTES_MAX}
                    />
                  </Field>

                  {error && <Alert title="Couldn't save">{error}</Alert>}
                </CardContent>

                <CardFooter className="justify-between">
                  {/* The action keeps its name through the whole flow; the
                      confirmation is a separate, quieter signal. */}
                  <p className="min-w-0 text-sm text-muted-foreground" aria-live="polite">
                    {saving ? (
                      "Saving…"
                    ) : justSaved ? (
                      <span className="inline-flex items-center gap-1.5 text-verified">
                        <Check className="size-3.5" /> Saved — applies to your next generation
                      </span>
                    ) : dirty ? (
                      "Unsaved changes"
                    ) : (
                      ""
                    )}
                  </p>
                  <Button type="submit" variant="accent" disabled={saving || !dirty}>
                    {saving && <Loader2 className="animate-spin" />}
                    Save brand kit
                  </Button>
                </CardFooter>
              </form>
            )}
          </Card>
        </FadeIn>

        <FadeIn delay={0.08} className="space-y-6 lg:sticky lg:top-20">
          <CreditsCard />

          <Card>
            <CardHeader>
              <CardTitle>How it reads</CardTitle>
            </CardHeader>
            <CardContent>
              {previewParts.length > 0 ? (
                <p className="text-sm leading-relaxed">
                  Every scene rendered with{" "}
                  <span className="font-medium">{previewParts.join(", ")}</span>
                  {notes.trim() ? (
                    <>
                      {" — "}
                      <span className="text-muted-foreground">{notes.trim()}</span>
                    </>
                  ) : (
                    "."
                  )}
                </p>
              ) : (
                <p className="text-sm text-muted-foreground">
                  Fill in a vibe, lighting, palette, or props to see how the studio will frame
                  every shot.
                </p>
              )}
            </CardContent>
          </Card>

          <AccountPanel />
        </FadeIn>
      </div>
    </div>
  );
}
