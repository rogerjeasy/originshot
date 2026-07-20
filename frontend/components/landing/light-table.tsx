"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { motion, useReducedMotion } from "framer-motion";
import { Check } from "lucide-react";

import { cn } from "@/lib/utils";
import { DEMO_ASSETS } from "@/lib/demo-assets";

/**
 * The signature element: a pack arriving on the viewing table, one frame at a
 * time, in the order the pipeline actually produces them.
 *
 * Everything here is real. The six frames are genuine OriginShot output served
 * from Backblaze B2, the model named against each one is the model that made it
 * (see backend/originshot_pipelines/registry.py), and the hash under each frame
 * is that object's true SHA-256 — click it and /verify resolves it against the
 * ledger. A visitor can check the page's central claim before signing up, which
 * is a stronger opening than any diagram of the claim would be.
 */

// Every frame here is the same ceramic mug, because the strip's caption claims
// exactly that. `variant-01` is deliberately NOT in this list: it is a green
// bottle — the "wrong item shipped" fixture from the resolve benchmark — and
// putting it under a "one source photo" claim would make the page's central
// argument false at a glance.
const SEQUENCE = [
  { slot: "studio-01", step: "studio", model: "gemini-3-pro-image-preview" },
  { slot: "lifestyle-02", step: "lifestyle", model: "gemini-3-pro-image-preview" },
  { slot: "scene-02", step: "in context", model: "gemini-3-pro-image-preview" },
  { slot: "lifestyle-05", step: "kitchen scene", model: "gemini-3-pro-image-preview" },
  { slot: "onmodel-01", step: "on-model", model: "gemini-3-pro-image-preview" },
  { slot: "video-01", step: "product video", model: "Kling-Image2Video-V2.1-Master" },
] as const;

const FRAME_MS = 900;
const HOLD_MS = 3600;

const FRAMES = SEQUENCE.map((s) => ({
  ...s,
  asset: DEMO_ASSETS.find((a) => a.slot === s.slot)!,
})).filter((f) => f.asset);

export function LightTable({ className }: { className?: string }) {
  const reduce = useReducedMotion();
  // `revealed` counts frames on the table. It runs 0 → 6, holds, and restarts.
  const [revealed, setRevealed] = useState(reduce ? FRAMES.length : 0);

  useEffect(() => {
    if (reduce) {
      setRevealed(FRAMES.length);
      return;
    }
    const done = revealed >= FRAMES.length;
    const t = setTimeout(
      () => setRevealed(done ? 0 : revealed + 1),
      done ? HOLD_MS : FRAME_MS,
    );
    return () => clearTimeout(t);
  }, [revealed, reduce]);

  const running = revealed < FRAMES.length;
  const current = FRAMES[Math.min(revealed, FRAMES.length - 1)];

  return (
    <figure className={cn("min-w-0", className)}>
      <div
        className="overflow-hidden rounded-xl border plate"
        style={{ backgroundColor: "var(--ink-2)" }}
      >
        {/* Rebate strip. The right-hand readout is the job log: it names the
            step being written and the model writing it, so the mechanism is
            legible rather than magic. */}
        <div className="flex items-center justify-between gap-3 border-b px-3.5 py-2.5">
          <span className="kicker on-ink-mute truncate">Pack 001 · ceramic mug</span>
          <span className="kicker flex shrink-0 items-center gap-1.5">
            {running ? (
              <>
                <span
                  aria-hidden
                  className="size-1.5 animate-pulse rounded-full"
                  style={{ backgroundColor: "var(--tungsten)" }}
                />
                <span className="t-accent hidden sm:inline">
                  writing {current.step}
                </span>
                <span className="t-accent sm:hidden">
                  {revealed + 1}/{FRAMES.length}
                </span>
              </>
            ) : (
              <>
                <Check className="t-verify size-3" />
                <span className="t-verify">6 frames · all verified</span>
              </>
            )}
          </span>
        </div>

        {/* Sequence progress, drawn in tungsten because it tracks work. */}
        <div className="h-px w-full" style={{ backgroundColor: "var(--ink-line)" }}>
          <motion.div
            className="h-px"
            style={{ backgroundColor: "var(--tungsten)" }}
            animate={{ width: `${(revealed / FRAMES.length) * 100}%` }}
            transition={{ duration: reduce ? 0 : 0.5, ease: "easeOut" }}
          />
        </div>

        {/* Two-up on phones: at three across, a 390px viewport gives each
            product photo about 120px, which is too small to judge the output —
            and judging the output is the only reason this panel exists. */}
        <div
          className="grid grid-cols-2 gap-px sm:grid-cols-3"
          style={{ backgroundColor: "var(--ink-line)" }}
        >
          {FRAMES.map((f, i) => {
            const on = i < revealed;
            const isNext = i === revealed && running;
            return (
              <Link
                key={f.slot}
                href={`/verify/${f.asset.sha}`}
                className="group relative block focus-visible:z-10"
                style={{ backgroundColor: "var(--ink-2)" }}
                aria-label={`Verify the ${f.step} frame — SHA-256 ${f.asset.sha.slice(0, 12)}`}
              >
                <div className="relative aspect-square overflow-hidden">
                  {/* The empty plate. Visible before its frame lands, so the
                      table reads as filling up rather than popping into being. */}
                  <div
                    className="absolute inset-0 grain opacity-40"
                    style={{ backgroundColor: "var(--ink-3)" }}
                    aria-hidden
                  />

                  {isNext && !reduce && (
                    <motion.div
                      aria-hidden
                      className="scan-bar absolute inset-x-0 h-1/3"
                      initial={{ top: "-33%" }}
                      animate={{ top: "100%" }}
                      transition={{ duration: FRAME_MS / 1000, ease: "linear" }}
                    />
                  )}

                  <motion.div
                    className="absolute inset-0"
                    initial={false}
                    animate={
                      on
                        ? { opacity: 1, scale: 1 }
                        : { opacity: 0, scale: reduce ? 1 : 1.06 }
                    }
                    transition={{ duration: reduce ? 0 : 0.5, ease: [0.2, 0, 0, 1] }}
                  >
                    {f.asset.style === "video" ? (
                      /* eslint-disable-next-line jsx-a11y/media-has-caption */
                      <video
                        src={f.asset.src}
                        className="size-full object-cover"
                        autoPlay
                        muted
                        loop
                        playsInline
                        preload="metadata"
                        aria-label="Five-second product video generated from the studio frame"
                      />
                    ) : (
                      /* eslint-disable-next-line @next/next/no-img-element */
                      <img
                        src={f.asset.src}
                        alt={`${f.step} frame generated by OriginShot from one source photo`}
                        width={f.asset.width}
                        height={f.asset.height}
                        className="size-full object-cover transition-transform duration-700 ease-out group-hover:scale-[1.05]"
                        loading={i < 3 ? "eager" : "lazy"}
                        fetchPriority={i === 0 ? "high" : "auto"}
                      />
                    )}
                  </motion.div>

                  {/* Step name, bottom-left, over a scrim so it holds on any
                      photograph. Fades in with its frame. */}
                  <motion.span
                    className="kicker absolute inset-x-0 bottom-0 flex items-center justify-between gap-1 bg-gradient-to-t from-black/75 to-transparent px-2 pb-1.5 pt-6 text-white/85"
                    initial={false}
                    animate={{ opacity: on ? 1 : 0 }}
                    transition={{ duration: reduce ? 0 : 0.3, delay: on && !reduce ? 0.15 : 0 }}
                  >
                    <span className="truncate">{f.step}</span>
                    <Check
                      className="t-verify size-3 shrink-0 opacity-0 transition-opacity group-hover:opacity-100"
                    />
                  </motion.span>
                </div>
              </Link>
            );
          })}
        </div>

        {/* The hash line. One frame's real SHA-256, cycling with the sequence —
            the claim and its evidence on the same surface. */}
        <div className="flex items-center gap-2 border-t px-3.5 py-2.5">
          <span className="kicker on-ink-mute shrink-0">sha-256</span>
          <motion.code
            key={current.slot}
            initial={reduce ? false : { opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ duration: 0.25 }}
            className="min-w-0 flex-1 truncate font-mono text-[11px]"
            style={{ color: "var(--ink-fg)" }}
          >
            {current.asset.sha}
          </motion.code>
        </div>
      </div>

      <figcaption className="on-ink-mute mt-3 text-[13px] leading-relaxed">
        Six real frames from one source photo, served from Backblaze B2. Open any frame to check
        its hash against the ledger.
      </figcaption>
    </figure>
  );
}
