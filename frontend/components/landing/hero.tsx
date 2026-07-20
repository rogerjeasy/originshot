"use client";

import Link from "next/link";
import { motion, useReducedMotion } from "framer-motion";
import { ArrowRight } from "lucide-react";

import { LightTable } from "./light-table";

/**
 * The hero opens on the product's actual output rather than a promise about it.
 *
 * The numbers below are derived, not decorative — they come straight from
 * backend/app/pricing.py: a full pack is studio 1 + lifestyle 2 + on-model 1 +
 * variants 2 + video 1 = 7 outputs, its ETA is the sum of _ETA_SECONDS (295s),
 * and $0.74 is estimate_styles() for all five styles. Keep them in step if the
 * cost model moves.
 */
const FACTS = [
  { v: "7", l: "assets per pack" },
  { v: "~5 min", l: "photo to catalog" },
  { v: "$0.74", l: "est. provider cost" },
  { v: "5", l: "marketplace presets" },
];

export function LandingHero() {
  const reduce = useReducedMotion();

  const rise = (delay: number) => ({
    initial: reduce ? { opacity: 0 } : { opacity: 0, y: 14 },
    animate: { opacity: 1, y: 0 },
    transition: { duration: 0.5, ease: [0.2, 0, 0, 1] as const, delay },
  });

  return (
    <section className="viewing-light relative overflow-hidden">
      <div className="relative mx-auto max-w-[1320px] px-5 pb-16 pt-10 sm:px-8 sm:pb-24 sm:pt-16">
        <div className="grid items-center gap-12 lg:grid-cols-[minmax(0,1.04fr)_minmax(0,1fr)] lg:gap-14">
          <div className="min-w-0">
            <motion.p {...rise(0)} className="kicker t-accent">
              For sellers with one good photo
            </motion.p>

            <motion.h1
              {...rise(0.06)}
              // Sized so "Sell it everywhere." holds one line from the lg
              // breakpoint up — at larger steps it broke to three ragged lines,
              // which read as an accident rather than a decision.
              className="display-face mt-5 text-[clamp(2.75rem,5.6vw,4rem)]"
            >
              Shoot it once.
              <br />
              <span className="on-ink-mute">Sell it everywhere.</span>
            </motion.h1>

            <motion.p
              {...rise(0.12)}
              className="on-ink-mute mt-6 max-w-xl text-pretty text-[17px] leading-relaxed"
            >
              OriginShot turns one phone photo into studio shots, lifestyle scenes, colour
              variants and a product video — and stamps every frame with a hash your buyer, or
              the marketplace, can check.
            </motion.p>

            <motion.div {...rise(0.18)} className="mt-9 flex flex-col gap-3 sm:flex-row">
              <Link
                href="/studio"
                className="btn-tungsten inline-flex h-12 items-center justify-center gap-2 rounded-lg px-7 text-[15px] font-semibold"
              >
                Generate your first pack
                <ArrowRight className="size-4" />
              </Link>
              <Link
                href="/pack"
                className="btn-on-ink inline-flex h-12 items-center justify-center rounded-lg px-7 text-[15px] font-medium"
              >
                See a real pack
              </Link>
            </motion.div>

            <motion.div {...rise(0.24)} className="mt-12">
              <div className="kelvin-rule" aria-hidden />
              <dl className="mt-6 grid grid-cols-2 gap-x-6 gap-y-7 sm:grid-cols-4">
                {FACTS.map((f) => (
                  <div key={f.l} className="min-w-0">
                    <dt className="display-face text-[1.75rem] tabular">{f.v}</dt>
                    <dd className="on-ink-mute mt-1.5 text-[13px] leading-snug">{f.l}</dd>
                  </div>
                ))}
              </dl>
            </motion.div>
          </div>

          <motion.div
            initial={reduce ? { opacity: 0 } : { opacity: 0, y: 22 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, ease: [0.2, 0, 0, 1], delay: 0.1 }}
            className="min-w-0"
          >
            <LightTable />
          </motion.div>
        </div>
      </div>
    </section>
  );
}
