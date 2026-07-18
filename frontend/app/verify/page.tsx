"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Hash, ShieldCheck, Upload } from "lucide-react";

import { apiFetch } from "@/lib/api";
import { cn } from "@/lib/utils";
import type { VerifyResult } from "@/lib/types";
import { AdaptiveChrome } from "@/components/adaptive-chrome";
import { FadeIn } from "@/components/motion/fade-in";
import { TamperDemo } from "@/components/tamper-demo";
import { UploadDropzone } from "@/components/upload-dropzone";
import { VerifyPanel } from "@/components/verify-panel";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { MediaSkeleton } from "@/components/ui/skeleton";

type Mode = "file" | "hash";

const SHA256 = /^[a-f0-9]{64}$/i;

const MODES: { id: Mode; label: string; icon: typeof Upload }[] = [
  { id: "file", label: "Upload a file", icon: Upload },
  { id: "hash", label: "Paste a hash", icon: Hash },
];

export default function VerifyHome() {
  const router = useRouter();
  const [mode, setMode] = useState<Mode>("file");
  const [sha, setSha] = useState("");
  const [shaError, setShaError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<VerifyResult | null>(null);

  async function verifyFile(file: File) {
    setBusy(true);
    setError(null);
    setResult(null);
    try {
      const fd = new FormData();
      fd.append("file", file);
      setResult(await apiFetch<VerifyResult>("/api/verify", { method: "POST", body: fd }));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Couldn't verify that file");
    } finally {
      setBusy(false);
    }
  }

  function submitHash(e: React.FormEvent) {
    e.preventDefault();
    const value = sha.trim();
    if (!SHA256.test(value)) {
      setShaError("A hash is 64 hexadecimal characters.");
      return;
    }
    setShaError(null);
    router.push(`/verify/${value.toLowerCase()}`);
  }

  return (
    <AdaptiveChrome>
      <div className="mx-auto max-w-2xl px-4 py-12 sm:px-6 sm:py-16">
        <FadeIn className="mb-8">
          <span className="grid size-11 place-items-center rounded-md border bg-card text-verified shadow-raised">
            <ShieldCheck className="size-5" />
          </span>
          <h1 className="mt-5 text-3xl font-semibold tracking-[-0.03em]">Verify provenance</h1>
          <p className="mt-3 text-muted-foreground">
            Drop a file and we re-hash the bytes and re-read its embedded manifest — no upload is
            kept. Or paste a SHA-256 to look it up in the ledger.
          </p>
        </FadeIn>

        {/* Two ways in, not a hierarchy — a segmented control, not tabs. */}
        <div
          role="radiogroup"
          aria-label="How do you want to verify?"
          className="mb-5 grid grid-cols-2 gap-1 rounded-md border bg-muted p-1"
        >
          {MODES.map(({ id, label, icon: Icon }) => {
            const on = mode === id;
            return (
              <button
                key={id}
                type="button"
                role="radio"
                aria-checked={on}
                onClick={() => {
                  setMode(id);
                  setResult(null);
                  setError(null);
                  setShaError(null);
                }}
                className={cn(
                  "inline-flex items-center justify-center gap-2 rounded-sm px-3 py-2 text-sm font-medium transition-colors",
                  on
                    ? "bg-card text-foreground shadow-raised"
                    : "text-muted-foreground hover:text-foreground",
                )}
              >
                <Icon className="size-4" />
                {label}
              </button>
            );
          })}
        </div>

        {mode === "file" ? (
          <div className="space-y-4">
            <UploadDropzone
              onFile={verifyFile}
              busy={busy}
              title="Drop a file to verify"
              subtitle="Image or video · we re-extract the manifest and re-hash the content"
              cta="Choose file"
              accept="image/*,video/mp4"
              requireImage={false}
            />
            {busy && <MediaSkeleton aspect="aspect-[3/1]" />}
            {error && <Alert title="Couldn't verify that file">{error}</Alert>}
            {result && (
              <FadeIn>
                <VerifyPanel result={result} />
              </FadeIn>
            )}
            <FadeIn delay={0.06}>
              <TamperDemo />
            </FadeIn>
          </div>
        ) : (
          <FadeIn>
            <form onSubmit={submitHash} className="space-y-2">
              <div className="flex flex-col gap-3 sm:flex-row">
                <Input
                  value={sha}
                  onChange={(e) => {
                    setSha(e.target.value);
                    if (shaError) setShaError(null);
                  }}
                  placeholder="64 hex characters"
                  className="font-mono sm:flex-1"
                  aria-label="SHA-256 hash"
                  aria-invalid={shaError ? true : undefined}
                  aria-describedby={shaError ? "sha-error" : undefined}
                  autoComplete="off"
                  spellCheck={false}
                />
                <Button type="submit" variant="accent">
                  Verify
                </Button>
              </div>
              {shaError && (
                <p id="sha-error" className="text-xs text-danger">
                  {shaError}
                </p>
              )}
            </form>
          </FadeIn>
        )}
      </div>
    </AdaptiveChrome>
  );
}
