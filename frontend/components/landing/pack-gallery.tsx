"use client";

import { useState } from "react";
import Link from "next/link";
import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import { ArrowUpRight } from "lucide-react";

import { cn } from "@/lib/utils";
import { PACK_GROUPS, framesFor } from "@/lib/pack";
import { Reveal, SectionHead } from "./section";

/**
 * What comes back from a run, grouped by where the seller is going to put it —
 * because that is how a seller decides whether this is worth their time. Every
 * frame is real output from a single source photo, which is also the argument:
 * switch tabs and it stays the same mug.
 *
 * This is the trailer for /pack, which shows the same run in full and lets you
 * inspect a frame's hash. The group data is shared from lib/pack so the two
 * surfaces can't disagree about what the run produced.
 */
export function PackGallery() {
  const [active, setActive] = useState<string>(PACK_GROUPS[0].id);
  const reduce = useReducedMotion();
  const group = PACK_GROUPS.find((g) => g.id === active) ?? PACK_GROUPS[0];
  const frames = framesFor(group);

  return (
    <section id="pack" className="band-paper scroll-mt-20">
      <div className="mx-auto max-w-[1320px] px-5 py-20 sm:px-8 sm:py-28">
        <Reveal>
          <SectionHead
            kicker="One source photo"
            title={
              <>
                Every frame here came from
                <br className="hidden sm:block" /> the same mug.
              </>
            }
            lede="No second shoot, no reshoot per marketplace. The pipeline reads the object once and holds onto it, so the thing you photographed is the thing that ships in every frame."
          />
        </Reveal>

        <Reveal delay={0.06}>
          <div
            className="mt-12 flex flex-wrap items-center gap-2"
            role="tablist"
            aria-label="Pack contents"
          >
            {PACK_GROUPS.map((g) => {
              const on = g.id === active;
              return (
                <button
                  key={g.id}
                  role="tab"
                  type="button"
                  aria-selected={on}
                  onClick={() => setActive(g.id)}
                  className={cn(
                    "relative rounded-full px-4 py-2 text-[13.5px] font-medium transition-colors",
                    on ? "text-[#16110a]" : "on-paper-mute hover:text-[var(--paper-fg)]",
                  )}
                >
                  {on && (
                    <motion.span
                      layoutId="pack-tab"
                      className="absolute inset-0 rounded-full"
                      style={{ backgroundColor: "var(--tungsten)" }}
                      transition={{ duration: reduce ? 0 : 0.3, ease: [0.2, 0, 0, 1] }}
                    />
                  )}
                  <span className="relative">{g.label}</span>
                </button>
              );
            })}
          </div>

          <div className="mt-6 flex flex-col gap-1.5 sm:flex-row sm:items-baseline sm:gap-4">
            <span className="kicker t-verify shrink-0">
              {group.goes}
            </span>
            <p className="on-paper-mute max-w-xl text-[15px]">{group.blurb}</p>
          </div>

          <AnimatePresence mode="wait">
            <motion.div
              key={group.id}
              initial={reduce ? { opacity: 0 } : { opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              exit={reduce ? { opacity: 0 } : { opacity: 0, y: -6 }}
              transition={{ duration: 0.28, ease: [0.2, 0, 0, 1] }}
              className={cn(
                "mt-8 grid gap-4",
                group.id === "motion" || group.id === "onmodel"
                  ? "max-w-sm grid-cols-1"
                  : "grid-cols-2 lg:grid-cols-4",
              )}
            >
              {frames.map((a) => (
                <Link
                  key={a.slot}
                  href={`/verify/${a.sha}`}
                  className="group relative block min-w-0 overflow-hidden rounded-lg border"
                  style={{ backgroundColor: "var(--paper-2)" }}
                  aria-label={`Verify this ${a.style} frame — SHA-256 ${a.sha.slice(0, 12)}`}
                >
                  <div
                    className={cn(
                      a.style === "lifestyle" || a.style === "onmodel"
                        ? "aspect-[4/5]"
                        : "aspect-square",
                    )}
                  >
                    {a.style === "video" ? (
                      /* eslint-disable-next-line jsx-a11y/media-has-caption */
                      <video
                        src={a.src}
                        className="size-full object-cover"
                        autoPlay
                        muted
                        loop
                        playsInline
                        preload="none"
                        aria-label="Five-second product video generated by OriginShot"
                      />
                    ) : (
                      /* eslint-disable-next-line @next/next/no-img-element */
                      <img
                        src={a.src}
                        alt={`${group.label} frame generated by OriginShot from one source photo`}
                        width={a.width}
                        height={a.height}
                        className="size-full object-cover transition-transform duration-700 ease-out group-hover:scale-[1.04]"
                        loading="lazy"
                      />
                    )}
                  </div>

                  {/* The hash surfaces on hover and on keyboard focus — the
                      evidence is one gesture away from every photograph on the
                      page, not quarantined in a trust section. */}
                  <span className="pointer-events-none absolute inset-x-0 bottom-0 flex translate-y-full items-center justify-between gap-2 bg-gradient-to-t from-black/80 to-black/0 px-2.5 pb-2 pt-8 opacity-0 transition-all duration-300 group-hover:translate-y-0 group-hover:opacity-100 group-focus-visible:translate-y-0 group-focus-visible:opacity-100">
                    <span className="truncate font-mono text-[10.5px] text-white/85">
                      {a.sha.slice(0, 16)}
                    </span>
                    <ArrowUpRight className="size-3.5 shrink-0 text-white/85" />
                  </span>
                </Link>
              ))}
            </motion.div>
          </AnimatePresence>

          {group.id === "motion" && (
            <p className="on-paper-mute mt-5 max-w-md text-[13px] leading-relaxed">
              Produced by <span className="font-mono">Kling-Image2Video-V2.1-Master</span> in
              4m 14s. The MP4 carries an embedded manifest and still verifies byte-for-byte.
            </p>
          )}

          <Link
            href="/pack"
            className="t-accent mt-10 inline-flex items-center gap-1.5 text-[14.5px] font-medium"
          >
            See the whole pack, frame by frame
            <ArrowUpRight className="size-4" />
          </Link>
        </Reveal>
      </div>
    </section>
  );
}
