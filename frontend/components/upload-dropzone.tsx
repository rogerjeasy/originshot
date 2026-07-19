"use client";

import { useRef, useState } from "react";
import { Loader2, UploadCloud } from "lucide-react";

import { cn } from "@/lib/utils";
import { Button } from "./ui/button";

/**
 * The single dropzone, used for one photo or many.
 *
 * `onFiles` opts into multi-select (Catalog Mode); `onFile` stays the single-photo contract
 * every existing caller uses. Kept as one component rather than two so the drag affordance,
 * the type guard and the disabled/busy states can't drift between the two entry points.
 */
export function UploadDropzone({
  onFile,
  onFiles,
  busy,
  title = "Drop a product photo",
  subtitle = "PNG / JPG / WebP, up to 25 MB · EXIF stripped on upload",
  cta = "Choose file",
  accept = "image/*",
  requireImage = true,
}: {
  onFile?: (file: File) => void;
  onFiles?: (files: File[]) => void;
  busy?: boolean;
  title?: string;
  subtitle?: string;
  cta?: string;
  accept?: string;
  requireImage?: boolean;
}) {
  const [drag, setDrag] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const multiple = Boolean(onFiles);

  function pick(list?: FileList | null) {
    const files = Array.from(list ?? []);
    if (!files.length) return;

    const images = requireImage ? files.filter((f) => f.type.startsWith("image/")) : files;
    if (!images.length) {
      setErr(files.length > 1 ? "None of those were image files." : "Please choose an image file.");
      return;
    }
    // Say what was dropped rather than silently thinning the selection — a seller who drags
    // a folder containing a stray PDF should know why they got 11 products and not 12.
    setErr(
      images.length < files.length
        ? `Skipped ${files.length - images.length} non-image file${
            files.length - images.length === 1 ? "" : "s"
          }.`
        : null,
    );

    if (onFiles) onFiles(images);
    else onFile?.(images[0]);
  }

  return (
    <div
      onDragOver={(e) => {
        e.preventDefault();
        setDrag(true);
      }}
      onDragLeave={() => setDrag(false)}
      onDrop={(e) => {
        e.preventDefault();
        setDrag(false);
        pick(e.dataTransfer.files);
      }}
      className={cn(
        "frame flex flex-col items-center justify-center gap-3 rounded-2xl border border-dashed p-10 text-center transition-colors",
        drag && "border-accent",
      )}
    >
      {busy ? (
        <Loader2 className="size-8 animate-spin text-accent" />
      ) : (
        <UploadCloud className="size-8 text-muted-foreground" />
      )}
      <div>
        <p className="font-medium">{title}</p>
        <p className="text-sm text-muted-foreground">{subtitle}</p>
      </div>
      <Button variant="outline" onClick={() => inputRef.current?.click()} disabled={busy}>
        {cta}
      </Button>
      {err && <p className="text-sm text-danger">{err}</p>}
      <input
        ref={inputRef}
        type="file"
        accept={accept}
        multiple={multiple}
        className="hidden"
        onChange={(e) => {
          pick(e.target.files);
          // Allow re-picking the same file(s) after a removal.
          e.target.value = "";
        }}
      />
    </div>
  );
}
