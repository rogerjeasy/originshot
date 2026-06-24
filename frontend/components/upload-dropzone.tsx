"use client";

import { useRef, useState } from "react";
import { Loader2, UploadCloud } from "lucide-react";

import { cn } from "@/lib/utils";
import { Button } from "./ui/button";

export function UploadDropzone({
  onFile,
  busy,
  title = "Drop a product photo",
  subtitle = "PNG / JPG / WebP, up to 25 MB · EXIF stripped on upload",
  cta = "Choose file",
  accept = "image/*",
  requireImage = true,
}: {
  onFile: (file: File) => void;
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

  function pick(file?: File | null) {
    if (!file) return;
    if (requireImage && !file.type.startsWith("image/")) {
      setErr("Please choose an image file.");
      return;
    }
    setErr(null);
    onFile(file);
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
        pick(e.dataTransfer.files?.[0]);
      }}
      className={cn(
        "studio-sweep frame flex flex-col items-center justify-center gap-3 rounded-2xl border border-dashed p-10 text-center transition-colors",
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
        className="hidden"
        onChange={(e) => pick(e.target.files?.[0])}
      />
    </div>
  );
}
