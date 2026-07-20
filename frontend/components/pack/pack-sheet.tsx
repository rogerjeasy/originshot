"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import { ArrowUpRight, Check, ChevronLeft, ChevronRight, Copy, X } from "lucide-react";

import { cn } from "@/lib/utils";
import type { DemoAsset } from "@/lib/demo-assets";
import { PACK_GROUPS, allFrames, framesFor, modelFor, type PackGroup } from "@/lib/pack";

/**
 * The contact sheet. Every frame the demo run produced, at a size you can
 * actually judge, with the inspector one click away — because the argument this
 * page is making ("these are real files, and you can check them") only lands if
 * the hash is reachable from the photograph rather than described near it.
 *
 * The landing gallery is the trailer for this; the difference is that here
 * nothing is hidden behind a tab by default.
 */

type Entry = { asset: DemoAsset; group: PackGroup };

const ALL = "all";

/** Portrait styles get a taller cell so the object isn't cropped to fit a square. */
function cellAspect(style: DemoAsset["style"]) {
  return style === "lifestyle" || style === "onmodel" ? "aspect-[4/5]" : "aspect-square";
}

function Media({
  asset,
  alt,
  className,
  eager,
}: {
  asset: DemoAsset;
  alt: string;
  className?: string;
  eager?: boolean;
}) {
  if (asset.style === "video") {
    return (
      /* eslint-disable-next-line jsx-a11y/media-has-caption */
      <video
        src={asset.src}
        className={className}
        autoPlay
        muted
        loop
        playsInline
        preload={eager ? "auto" : "none"}
        aria-label={alt}
      />
    );
  }
  return (
    /* eslint-disable-next-line @next/next/no-img-element */
    <img
      src={asset.src}
      alt={alt}
      width={asset.width}
      height={asset.height}
      className={className}
      loading={eager ? "eager" : "lazy"}
    />
  );
}

function CopyHash({ sha }: { sha: string }) {
  const [done, setDone] = useState(false);

  useEffect(() => {
    if (!done) return;
    const t = setTimeout(() => setDone(false), 1600);
    return () => clearTimeout(t);
  }, [done]);

  return (
    <button
      type="button"
      onClick={async () => {
        try {
          await navigator.clipboard.writeText(sha);
          setDone(true);
        } catch {
          /* Clipboard is blocked in some embedded browsers — the hash is
             selectable text either way, so this stays silent. */
        }
      }}
      className="btn-on-ink inline-flex h-9 shrink-0 items-center gap-1.5 rounded-md px-3 text-[13px] font-medium"
    >
      {done ? <Check className="size-3.5" /> : <Copy className="size-3.5" />}
      {done ? "Copied" : "Copy"}
    </button>
  );
}

function Inspector({
  entry,
  onClose,
  onStep,
}: {
  entry: Entry;
  onClose: () => void;
  onStep: (delta: number) => void;
}) {
  const { asset, group } = entry;
  const reduce = useReducedMotion();
  const panel = useRef<HTMLDivElement>(null);

  // Escape closes, arrows walk the sheet — the inspector is meant to be paged
  // through like a real contact sheet, not opened and dismissed one at a time.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
      if (e.key === "ArrowRight") onStep(1);
      if (e.key === "ArrowLeft") onStep(-1);
    };
    window.addEventListener("keydown", onKey);
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    panel.current?.focus();
    return () => {
      window.removeEventListener("keydown", onKey);
      document.body.style.overflow = prev;
    };
  }, [onClose, onStep]);

  const rows: [string, React.ReactNode][] = [
    ["style", <span key="s" className="t-verify font-mono">{asset.style}</span>],
    ["destination", group.goes],
    ["dimensions", `${asset.width} × ${asset.height}`],
    ["model", <span key="m" className="font-mono text-[12.5px]">{modelFor(asset.style)}</span>],
  ];

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      transition={{ duration: reduce ? 0 : 0.2 }}
      className="fixed inset-0 z-50 flex items-center justify-center p-4 sm:p-8"
      style={{ backgroundColor: "color-mix(in srgb, var(--ink) 86%, transparent)" }}
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <motion.div
        ref={panel}
        tabIndex={-1}
        role="dialog"
        aria-modal="true"
        aria-label={`${group.label} frame — SHA-256 ${asset.sha.slice(0, 12)}`}
        initial={reduce ? { opacity: 0 } : { opacity: 0, y: 16, scale: 0.985 }}
        animate={{ opacity: 1, y: 0, scale: 1 }}
        exit={reduce ? { opacity: 0 } : { opacity: 0, y: 10, scale: 0.99 }}
        transition={{ duration: reduce ? 0 : 0.26, ease: [0.2, 0, 0, 1] }}
        className="band-ink relative grid max-h-full w-full max-w-5xl overflow-hidden rounded-xl border outline-none lg:grid-cols-[minmax(0,1.15fr)_22rem]"
        style={{ backgroundColor: "var(--ink-2)" }}
      >
        <div
          className="flex min-h-0 items-center justify-center overflow-hidden p-3 sm:p-5"
          style={{ backgroundColor: "var(--ink)" }}
        >
          <Media
            asset={asset}
            alt={`${group.label} frame generated by OriginShot from one source photo`}
            eager
            className="max-h-[46vh] w-auto max-w-full rounded-lg object-contain lg:max-h-[74vh]"
          />
        </div>

        <div className="flex min-h-0 flex-col overflow-y-auto p-6">
          <p className="kicker t-accent">{group.label}</p>
          <h2 className="display-face mt-3 text-[1.5rem]">{asset.slot}</h2>

          <dl className="mt-6 grid gap-3.5">
            {rows.map(([k, v]) => (
              <div key={k} className="flex items-baseline justify-between gap-4 border-t pt-3">
                <dt className="kicker on-ink-mute shrink-0">{k}</dt>
                <dd className="min-w-0 truncate text-right text-[13.5px]">{v}</dd>
              </div>
            ))}
          </dl>

          <div className="mt-6 border-t pt-4">
            <p className="kicker on-ink-mute">sha-256</p>
            <div className="mt-2.5 flex items-start gap-2">
              <code className="on-ink-mute min-w-0 flex-1 break-all font-mono text-[11.5px] leading-relaxed">
                {asset.sha}
              </code>
              <CopyHash sha={asset.sha} />
            </div>
          </div>

          <Link
            href={`/verify/${asset.sha}`}
            className="btn-tungsten mt-6 inline-flex h-11 items-center justify-center gap-2 rounded-lg px-5 text-[14.5px] font-semibold"
          >
            Verify this file
            <ArrowUpRight className="size-4" />
          </Link>
          <p className="on-ink-mute mt-3 text-[12.5px] leading-relaxed">
            Resolves against the provenance manifest written when this frame was generated. You
            can also drop the file itself into <span className="font-mono">/verify</span> — the
            bytes are checked, not the filename.
          </p>
        </div>

        {/* Controls sit over the media pane so they stay reachable at every
            breakpoint without a second toolbar. */}
        <div className="absolute right-3 top-3 flex gap-1.5">
          <button
            type="button"
            onClick={() => onStep(-1)}
            aria-label="Previous frame"
            className="btn-on-ink grid size-9 place-items-center rounded-md"
          >
            <ChevronLeft className="size-4" />
          </button>
          <button
            type="button"
            onClick={() => onStep(1)}
            aria-label="Next frame"
            className="btn-on-ink grid size-9 place-items-center rounded-md"
          >
            <ChevronRight className="size-4" />
          </button>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close"
            className="btn-on-ink grid size-9 place-items-center rounded-md"
          >
            <X className="size-4" />
          </button>
        </div>
      </motion.div>
    </motion.div>
  );
}

export function PackSheet() {
  const [filter, setFilter] = useState<string>(ALL);
  const [openSlot, setOpenSlot] = useState<string | null>(null);
  const reduce = useReducedMotion();

  const everything = useMemo(() => allFrames(), []);
  const shown = useMemo(
    () =>
      filter === ALL
        ? everything
        : everything.filter((e) => e.group.id === filter),
    [everything, filter],
  );

  // The inspector pages through what is currently on screen, so stepping never
  // lands on a frame the filter has hidden.
  const openIndex = shown.findIndex((e) => e.asset.slot === openSlot);
  const open = openIndex >= 0 ? shown[openIndex] : null;

  const step = useCallback(
    (delta: number) => {
      if (openIndex < 0 || shown.length === 0) return;
      const next = (openIndex + delta + shown.length) % shown.length;
      setOpenSlot(shown[next].asset.slot);
    },
    [openIndex, shown],
  );

  const tabs = [{ id: ALL, label: "All frames", count: everything.length }].concat(
    PACK_GROUPS.map((g) => ({ id: g.id, label: g.label, count: framesFor(g).length })),
  );

  const active = PACK_GROUPS.find((g) => g.id === filter);

  return (
    <div>
      <div className="flex flex-wrap items-center gap-2" role="tablist" aria-label="Pack contents">
        {tabs.map((t) => {
          const on = t.id === filter;
          return (
            <button
              key={t.id}
              role="tab"
              type="button"
              aria-selected={on}
              onClick={() => setFilter(t.id)}
              className={cn(
                "relative rounded-full px-4 py-2 text-[13.5px] font-medium transition-colors",
                on ? "text-[#16110a]" : "on-paper-mute hover:text-[var(--paper-fg)]",
              )}
            >
              {on && (
                <motion.span
                  layoutId="pack-sheet-tab"
                  className="absolute inset-0 rounded-full"
                  style={{ backgroundColor: "var(--tungsten)" }}
                  transition={{ duration: reduce ? 0 : 0.3, ease: [0.2, 0, 0, 1] }}
                />
              )}
              <span className="relative">
                {t.label}
                <span className="tabular ml-1.5 opacity-60">{t.count}</span>
              </span>
            </button>
          );
        })}
      </div>

      {/* The filter's own argument. On "All frames" this is the sheet-level
          claim; on a group it is that group's reason to exist. */}
      <div className="mt-7 flex flex-col gap-1.5 sm:flex-row sm:gap-5">
        <span className="kicker t-verify shrink-0 sm:pt-1">
          {active ? active.goes : "One source photo"}
        </span>
        <p className="on-paper-mute max-w-2xl text-[15px] leading-relaxed">
          {active
            ? active.detail
            : "Every frame below came back from the same source photograph of the same mug. Nothing here was retouched, re-cropped or hand-picked from a larger set — this is the run's output, in full. Click any frame to read its hash."}
        </p>
      </div>

      <div className="mt-9 grid grid-cols-2 gap-4 lg:grid-cols-4">
        {shown.map(({ asset, group }) => (
          <motion.button
            key={asset.slot}
            layout={!reduce}
            type="button"
            onClick={() => setOpenSlot(asset.slot)}
            aria-label={`Inspect ${group.label} frame — SHA-256 ${asset.sha.slice(0, 12)}`}
            className="group relative block min-w-0 overflow-hidden rounded-lg border text-left"
            style={{ backgroundColor: "var(--paper-2)" }}
            transition={{ duration: reduce ? 0 : 0.3, ease: [0.2, 0, 0, 1] }}
          >
            <div className={cellAspect(asset.style)}>
              <Media
                asset={asset}
                alt={`${group.label} frame generated by OriginShot from one source photo`}
                className="size-full object-cover transition-transform duration-700 ease-out group-hover:scale-[1.04]"
              />
            </div>

            <span className="pointer-events-none absolute inset-x-0 bottom-0 flex translate-y-full items-center justify-between gap-2 bg-gradient-to-t from-black/80 to-black/0 px-2.5 pb-2 pt-8 opacity-0 transition-all duration-300 group-hover:translate-y-0 group-hover:opacity-100 group-focus-visible:translate-y-0 group-focus-visible:opacity-100">
              <span className="truncate font-mono text-[10.5px] text-white/85">
                {asset.sha.slice(0, 16)}
              </span>
              <ArrowUpRight className="size-3.5 shrink-0 text-white/85" />
            </span>
          </motion.button>
        ))}
      </div>

      <AnimatePresence>
        {open && (
          <Inspector
            key={open.asset.slot}
            entry={open}
            onClose={() => setOpenSlot(null)}
            onStep={step}
          />
        )}
      </AnimatePresence>
    </div>
  );
}
