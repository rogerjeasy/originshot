"use client";

import { useEffect } from "react";
import Link from "next/link";
import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import { RotateCcw, ShieldCheck, Sparkles, X } from "lucide-react";

import { shortHash } from "@/lib/utils";
import type { Asset } from "@/lib/types";
import { Button } from "./ui/button";

export function Lightbox({
  asset,
  onClose,
  onReplay,
  replayDisabled = false,
  linkToProduct = false,
}: {
  asset: Asset | null;
  onClose: () => void;
  /** Re-run this asset from its stored manifest. Omit where replay makes no sense. */
  onReplay?: (a: Asset) => void;
  replayDisabled?: boolean;
  /** Show an "Open product" link — for surfaces outside the SKU workspace (Library). */
  linkToProduct?: boolean;
}) {
  const reduce = useReducedMotion();

  // Replay needs a spec to execute: a stored manifest, on a generated image. The authentic
  // original is a photograph, and video's input was a generated intermediate — the backend
  // refuses both, so the button never appears for them.
  const canReplay = Boolean(
    asset && onReplay && !asset.is_authentic && asset.manifest_key && asset.style !== "video",
  );

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") onClose();
    }
    if (asset) {
      document.addEventListener("keydown", onKey);
      return () => document.removeEventListener("keydown", onKey);
    }
  }, [asset, onClose]);

  return (
    <AnimatePresence>
      {asset && (
        <motion.div
          role="dialog"
          aria-modal="true"
          aria-label={`${asset.style} preview`}
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4"
          onClick={onClose}
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.18, ease: "easeOut" }}
        >
          <motion.div
            className="flex max-h-[90dvh] w-full max-w-3xl flex-col overflow-hidden rounded-2xl border bg-card"
            onClick={(e) => e.stopPropagation()}
            initial={reduce ? { opacity: 0 } : { opacity: 0, scale: 0.97, y: 8 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={reduce ? { opacity: 0 } : { opacity: 0, scale: 0.97, y: 8 }}
            transition={{ type: "spring", stiffness: 320, damping: 28 }}
          >
            <div className="flex items-center justify-between border-b p-3">
              <span className="truncate text-sm font-medium capitalize">{asset.style}</span>
              <Button variant="ghost" size="icon" onClick={onClose} aria-label="Close">
                <X />
              </Button>
            </div>
            <div className="grid min-h-0 flex-1 place-items-center overflow-auto bg-muted">
              {asset.modality === "video" ? (
                // eslint-disable-next-line jsx-a11y/media-has-caption
                <video src={asset.url ?? undefined} controls className="max-h-[60dvh] max-w-full" />
              ) : (
                // eslint-disable-next-line @next/next/no-img-element
                <img
                  src={asset.url ?? undefined}
                  alt={asset.style}
                  className="max-h-[60dvh] max-w-full object-contain"
                />
              )}
            </div>
            <div className="space-y-2 border-t p-4 text-sm">
              <div className="flex flex-wrap items-center gap-x-4 gap-y-1 font-mono text-xs text-muted-foreground">
                <span>sha256 {shortHash(asset.sha256, 8, 8)}</span>
                {asset.provider && <span>{asset.provider}</span>}
                {asset.model && <span>{asset.model}</span>}
                {asset.embedded && <span className="text-verified">manifest embedded</span>}
                {asset.replay_of && <span>replay of {shortHash(asset.replay_of, 8, 8)}</span>}
              </div>
              <div className="flex flex-wrap items-center justify-between gap-2">
                <span className="inline-flex items-center gap-1.5">
                  {asset.is_authentic ? (
                    <ShieldCheck className="size-4 text-verified" />
                  ) : (
                    <Sparkles className="size-4" />
                  )}
                  {asset.is_authentic ? "Verified original" : "AI-generated"}
                </span>
                <span className="inline-flex items-center gap-3">
                  {linkToProduct && (
                    <Link
                      href={`/studio/${asset.sku_id}`}
                      className="text-accent hover:underline"
                    >
                      Open product →
                    </Link>
                  )}
                  {canReplay && (
                    <Button
                      variant="outline"
                      size="sm"
                      className="gap-1.5"
                      disabled={replayDisabled}
                      onClick={() => onReplay?.(asset)}
                      title="Re-run this exact generation from its embedded provenance spec — same prompt, model and seed, fresh output"
                    >
                      <RotateCcw className="size-3.5" />
                      Replay from manifest
                    </Button>
                  )}
                  <Link href={`/verify/${asset.sha256}`} className="text-accent hover:underline">
                    Verify →
                  </Link>
                </span>
              </div>
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
