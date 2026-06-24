"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { motion } from "framer-motion";
import { Hash, ShieldCheck, Upload } from "lucide-react";

import { apiFetch } from "@/lib/api";
import type { VerifyResult } from "@/lib/types";
import { AdaptiveChrome } from "@/components/adaptive-chrome";
import { FadeIn } from "@/components/motion/fade-in";
import { UploadDropzone } from "@/components/upload-dropzone";
import { VerifyPanel } from "@/components/verify-panel";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";

type Mode = "file" | "hash";

export default function VerifyHome() {
  const router = useRouter();
  const [mode, setMode] = useState<Mode>("file");
  const [sha, setSha] = useState("");
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
      setError(e instanceof Error ? e.message : "Verification failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <AdaptiveChrome>
      <div className="mx-auto max-w-xl px-4 py-12 sm:px-6 sm:py-16">
        <FadeIn className="mb-6 text-center">
            <span className="mx-auto grid size-14 place-items-center rounded-2xl border bg-card shadow-sm">
              <ShieldCheck className="size-7 text-verified" />
            </span>
            <h1 className="mt-4 text-2xl font-semibold tracking-tight">Verify provenance</h1>
            <p className="text-muted-foreground">
              Drop a file to re-check its embedded manifest from the bytes, or paste a SHA-256.
            </p>
          </FadeIn>

          <div className="mb-4 grid grid-cols-2 gap-1 rounded-lg bg-secondary p-1">
            {(["file", "hash"] as Mode[]).map((m) => (
              <button
                key={m}
                type="button"
                onClick={() => {
                  setMode(m);
                  setResult(null);
                  setError(null);
                }}
                className={cn(
                  "relative inline-flex items-center justify-center gap-1.5 rounded-md px-3 py-1.5 text-sm font-medium transition-colors",
                  mode === m ? "text-foreground" : "text-muted-foreground hover:text-foreground",
                )}
              >
                {mode === m && (
                  <motion.span
                    layoutId="verify-tab"
                    className="absolute inset-0 rounded-md bg-card shadow-sm"
                    transition={{ type: "spring", stiffness: 380, damping: 32 }}
                  />
                )}
                <span className="relative inline-flex items-center gap-1.5">
                  {m === "file" ? <Upload className="size-4" /> : <Hash className="size-4" />}
                  {m === "file" ? "Upload a file" : "Paste a hash"}
                </span>
              </button>
            ))}
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
              {busy && <div className="shimmer frame h-48 rounded-xl border bg-muted" />}
              {error && <Alert>{error}</Alert>}
              {result && (
                <FadeIn>
                  <VerifyPanel result={result} />
                </FadeIn>
              )}
            </div>
          ) : (
            <FadeIn>
              <Card>
                <CardContent className="pt-5">
                  <form
                    onSubmit={(e) => {
                      e.preventDefault();
                      if (sha.trim()) router.push(`/verify/${sha.trim()}`);
                    }}
                    className="flex flex-col gap-3 sm:flex-row"
                  >
                    <Input
                      value={sha}
                      onChange={(e) => setSha(e.target.value)}
                      placeholder="sha256…"
                      className="font-mono sm:flex-1"
                      aria-label="SHA-256 hash"
                    />
                    <Button type="submit" variant="accent">
                      Verify
                    </Button>
                  </form>
                </CardContent>
              </Card>
            </FadeIn>
          )}
      </div>
    </AdaptiveChrome>
  );
}
