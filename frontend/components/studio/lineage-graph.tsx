"use client";

import Link from "next/link";
import { ArrowUpRight, ShieldCheck, Sparkles } from "lucide-react";

import { cn } from "@/lib/utils";
import type { Asset } from "@/lib/types";

const STYLE_ORDER = ["studio", "lifestyle", "onmodel", "variant", "video"];

const STYLE_LABEL: Record<string, string> = {
  studio: "Studio",
  lifestyle: "Lifestyle",
  onmodel: "On model",
  variant: "Variant",
  video: "Video",
};

function short(sha: string): string {
  return `${sha.slice(0, 8)}…${sha.slice(-4)}`;
}

function HashChip({ sha }: { sha: string }) {
  return (
    <Link
      href={`/verify/${sha}`}
      className="inline-flex items-center gap-1 rounded-full border bg-card px-2 py-0.5 font-mono text-[11px] t-accent transition-colors hover:border-accent/40"
      title={`Verify ${sha}`}
    >
      {short(sha)}
      <ArrowUpRight className="size-3" />
    </Link>
  );
}

/**
 * The provenance chain as a navigable tree: the authentic original at the root, every
 * generated asset hanging off it, each node carrying its content hash as a link into the
 * public verifier. The bucket keys ARE these hashes — this diagram is the storage layout,
 * not an illustration of it.
 */
export function LineageGraph({ assets }: { assets: Asset[] }) {
  const original = assets.find((a) => a.is_authentic);
  const generated = assets
    .filter((a) => !a.is_authentic && a.sha256)
    .sort(
      (a, b) =>
        STYLE_ORDER.indexOf(a.style) - STYLE_ORDER.indexOf(b.style) ||
        a.created_at.localeCompare(b.created_at),
    );

  if (!original || generated.length === 0) return null;

  return (
    <section className="rounded-lg border bg-card p-5">
      <div className="mb-4 flex items-baseline justify-between gap-3">
        <h3 className="label text-foreground">Provenance chain</h3>
        <span className="font-mono text-[11px] text-muted-foreground">
          every hash resolves in /verify
        </span>
      </div>

      {/* Root: the anchored original. */}
      <div className="flex flex-wrap items-center gap-2.5">
        <span className="grid size-7 shrink-0 place-items-center rounded-md border bg-verified-surface text-verified">
          <ShieldCheck className="size-3.5" />
        </span>
        <span className="text-sm font-medium">Authentic original</span>
        <HashChip sha={original.sha256} />
        <span className="font-mono text-[11px] text-muted-foreground">
          SHA-256 anchored on upload
        </span>
      </div>

      {/* Children on a rail — the tree the content addresses actually form. */}
      <ul className="ms-3.5 mt-1 border-s ps-5">
        {generated.map((a) => (
          <li key={a.id} className="relative py-2">
            <span
              aria-hidden
              className="absolute -start-5 top-1/2 h-px w-4 bg-border"
            />
            <div className="flex flex-wrap items-center gap-x-2.5 gap-y-1">
              <span className="grid size-6 shrink-0 place-items-center rounded-md border bg-muted text-muted-foreground">
                <Sparkles className="size-3" />
              </span>
              <span className="w-16 text-sm">{STYLE_LABEL[a.style] ?? a.style}</span>
              <HashChip sha={a.sha256} />
              {(a.provider || a.model) && (
                <span className="min-w-0 truncate font-mono text-[11px] text-muted-foreground">
                  {[a.provider, a.model].filter(Boolean).join(" · ")}
                </span>
              )}
              {a.qa && (
                <span
                  className={cn(
                    "font-mono text-[11px]",
                    a.qa.passed ? "text-verified" : "text-warning",
                  )}
                >
                  {a.qa.passed ? "QA ✓" : "QA ⚠"}
                </span>
              )}
            </div>
          </li>
        ))}
      </ul>

      <p className="mt-3 border-t pt-3 text-[11px] leading-relaxed text-muted-foreground">
        Bucket keys are the SHA-256 of the content, so this tree is the B2 storage layout
        itself: identical bytes are stored exactly once, and every node above can be
        re-verified from its own bytes.
      </p>
    </section>
  );
}
