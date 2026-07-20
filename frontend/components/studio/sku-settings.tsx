"use client";

import { useState } from "react";
import { Loader2, Pencil, Trash2, TriangleAlert } from "lucide-react";

import { apiFetch, ApiError } from "@/lib/api";
import type { Sku } from "@/lib/types";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Dialog, DialogBody, DialogClose, DialogContent } from "@/components/ui/dialog";
import { Input, Textarea } from "@/components/ui/input";

/**
 * Edit + delete controls for a single product (SKU), sharing one pair of dialogs.
 *
 * Deletion is destructive and, for a product with a generated pack, throws away real work —
 * so it is guarded by an explicit confirmation that states exactly what goes (and what does
 * NOT: the provenance a file already carries, and its entry in the transparency log, both
 * outlive the delete). Editing is the low-stakes counterpart and opens inline.
 *
 * The component is presentation-only about *where* the buttons sit (`layout`); the mutations
 * and their optimistic callbacks are identical in every placement.
 */
export function SkuSettings({
  sku,
  assetCount = 0,
  onSaved,
  onDeleted,
  layout = "buttons",
}: {
  sku: Sku;
  /** Generated assets that will be removed with the product — surfaced in the warning. */
  assetCount?: number;
  onSaved?: (updated: Sku) => void;
  onDeleted?: () => void;
  layout?: "buttons" | "icons";
}) {
  const [editOpen, setEditOpen] = useState(false);
  const [deleteOpen, setDeleteOpen] = useState(false);

  return (
    <>
      {layout === "icons" ? (
        <div className="flex items-center gap-1">
          <IconButton label="Edit product" onClick={() => setEditOpen(true)}>
            <Pencil className="size-4" />
          </IconButton>
          <IconButton label="Delete product" danger onClick={() => setDeleteOpen(true)}>
            <Trash2 className="size-4" />
          </IconButton>
        </div>
      ) : (
        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm" onClick={() => setEditOpen(true)}>
            <Pencil /> Edit
          </Button>
          <Button variant="ghost" size="sm" onClick={() => setDeleteOpen(true)}>
            <Trash2 /> Delete
          </Button>
        </div>
      )}

      <EditSkuDialog
        sku={sku}
        open={editOpen}
        onOpenChange={setEditOpen}
        onSaved={(u) => {
          setEditOpen(false);
          onSaved?.(u);
        }}
      />
      <DeleteSkuDialog
        sku={sku}
        assetCount={assetCount}
        open={deleteOpen}
        onOpenChange={setDeleteOpen}
        onDeleted={() => {
          setDeleteOpen(false);
          onDeleted?.();
        }}
      />
    </>
  );
}

function IconButton({
  children,
  label,
  danger,
  onClick,
}: {
  children: React.ReactNode;
  label: string;
  danger?: boolean;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      aria-label={label}
      title={label}
      onClick={(e) => {
        // These sit on top of the card's navigational link — never let the click bubble
        // into a route change or the Radix dialog opens and immediately navigates away.
        e.preventDefault();
        e.stopPropagation();
        onClick();
      }}
      className={`grid size-8 place-items-center rounded-md border bg-card/90 text-muted-foreground shadow-raised backdrop-blur transition-colors hover:text-foreground ${
        danger ? "hover:border-danger/40 hover:text-danger" : "hover:bg-secondary"
      }`}
    >
      {children}
    </button>
  );
}

// ── Edit ───────────────────────────────────────────────────────────────
export function EditSkuDialog({
  sku,
  open,
  onOpenChange,
  onSaved,
}: {
  sku: Sku;
  open: boolean;
  onOpenChange: (v: boolean) => void;
  onSaved: (updated: Sku) => void;
}) {
  const [title, setTitle] = useState(sku.title);
  const [category, setCategory] = useState(sku.category ?? "");
  const [description, setDescription] = useState(sku.description ?? "");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Re-seed the form whenever a different product's dialog opens.
  const seedKey = `${sku.id}:${open}`;
  const [seeded, setSeeded] = useState("");
  if (open && seeded !== seedKey) {
    setSeeded(seedKey);
    setTitle(sku.title);
    setCategory(sku.category ?? "");
    setDescription(sku.description ?? "");
    setError(null);
  }

  async function save(e: React.FormEvent) {
    e.preventDefault();
    if (!title.trim()) return;
    setSaving(true);
    setError(null);
    try {
      // Send only what changed; "" clears an optional field, which the API accepts for
      // category/description (but not title, which stays required).
      const patch: Record<string, string> = {};
      if (title !== sku.title) patch.title = title.trim();
      if (category !== (sku.category ?? "")) patch.category = category.trim();
      if (description !== (sku.description ?? "")) patch.description = description.trim();
      if (Object.keys(patch).length === 0) {
        onOpenChange(false);
        return;
      }
      const updated = await apiFetch<Sku>(`/api/skus/${sku.id}`, {
        method: "PATCH",
        body: JSON.stringify(patch),
      });
      onSaved(updated);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Couldn't save changes");
    } finally {
      setSaving(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <form onSubmit={save} className="flex min-h-0 flex-col">
          <div className="flex flex-col gap-1 border-b p-5 pe-12">
            <h2 className="text-base font-semibold tracking-tight">Edit product</h2>
            <p className="text-sm text-muted-foreground">
              These details drive the generated pack&apos;s prompts and listing copy.
            </p>
          </div>
          <DialogBody className="space-y-4">
            <Field label="Title" htmlFor="sku-title">
              <Input
                id="sku-title"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                maxLength={140}
                required
                placeholder="e.g. Handmade ceramic mug"
              />
            </Field>
            <Field label="Category" htmlFor="sku-category" hint="optional">
              <Input
                id="sku-category"
                value={category}
                onChange={(e) => setCategory(e.target.value)}
                maxLength={80}
                placeholder="e.g. Home & Kitchen"
              />
            </Field>
            <Field label="Description" htmlFor="sku-description" hint="optional">
              <Textarea
                id="sku-description"
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                maxLength={2000}
                rows={4}
                placeholder="What the product is — shapes the AI's understanding of it."
              />
            </Field>
            {error && <Alert title="Couldn't save changes">{error}</Alert>}
          </DialogBody>
          <div className="flex flex-col-reverse gap-2 border-t bg-muted/40 p-4 sm:flex-row sm:justify-end">
            <DialogClose asChild>
              <Button type="button" variant="ghost">
                Cancel
              </Button>
            </DialogClose>
            <Button type="submit" variant="accent" disabled={saving || !title.trim()}>
              {saving ? <Loader2 className="animate-spin" /> : null} Save changes
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
}

// ── Delete ─────────────────────────────────────────────────────────────
export function DeleteSkuDialog({
  sku,
  assetCount,
  open,
  onOpenChange,
  onDeleted,
}: {
  sku: Sku;
  assetCount: number;
  open: boolean;
  onOpenChange: (v: boolean) => void;
  onDeleted: () => void;
}) {
  const [deleting, setDeleting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function confirm() {
    setDeleting(true);
    setError(null);
    try {
      await apiFetch(`/api/skus/${sku.id}`, { method: "DELETE" });
      onDeleted();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Couldn't delete this product");
    } finally {
      setDeleting(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <div className="flex flex-col gap-1 border-b p-5 pe-12">
          <h2 className="flex items-center gap-2 text-base font-semibold tracking-tight">
            <TriangleAlert className="size-4 text-danger" />
            Delete “{sku.title}”?
          </h2>
        </div>
        <DialogBody className="space-y-3 text-sm text-muted-foreground">
          <p>
            This permanently removes the product
            {assetCount > 0 ? (
              <>
                {" "}
                and its <span className="font-medium text-foreground">{assetCount}</span>{" "}
                generated asset{assetCount === 1 ? "" : "s"}
              </>
            ) : null}
            . This can&apos;t be undone.
          </p>
          <p>
            Files you&apos;ve already downloaded keep their embedded provenance, and the
            transparency log is append-only — a deleted asset&apos;s entry stays, because it
            records that the file <em>was</em> made.
          </p>
          {error && <Alert title="Couldn't delete this product">{error}</Alert>}
        </DialogBody>
        <div className="flex flex-col-reverse gap-2 border-t bg-muted/40 p-4 sm:flex-row sm:justify-end">
          <DialogClose asChild>
            <Button type="button" variant="ghost">
              Cancel
            </Button>
          </DialogClose>
          <Button type="button" variant="destructive" onClick={confirm} disabled={deleting}>
            {deleting ? <Loader2 className="animate-spin" /> : <Trash2 />} Delete product
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}

function Field({
  label,
  htmlFor,
  hint,
  children,
}: {
  label: string;
  htmlFor: string;
  hint?: string;
  children: React.ReactNode;
}) {
  return (
    <div className="space-y-1.5">
      <label htmlFor={htmlFor} className="flex items-baseline justify-between text-sm font-medium">
        {label}
        {hint && <span className="text-xs font-normal text-muted-foreground">{hint}</span>}
      </label>
      {children}
    </div>
  );
}
