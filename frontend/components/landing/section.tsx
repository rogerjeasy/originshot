"use client";

import { motion, useReducedMotion } from "framer-motion";

import { cn } from "@/lib/utils";

/** Scroll-triggered reveal, used once per section rather than per element —
 *  a whole band settling reads calmer than a dozen things arriving separately. */
export function Reveal({
  children,
  className,
  delay = 0,
}: {
  children: React.ReactNode;
  className?: string;
  delay?: number;
}) {
  const reduce = useReducedMotion();
  return (
    <motion.div
      className={className}
      initial={reduce ? { opacity: 0 } : { opacity: 0, y: 18 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, margin: "-80px" }}
      transition={{ duration: 0.55, ease: [0.2, 0, 0, 1], delay }}
    >
      {children}
    </motion.div>
  );
}

export function SectionHead({
  kicker,
  title,
  lede,
  tone = "paper",
  className,
}: {
  kicker: string;
  title: React.ReactNode;
  lede?: React.ReactNode;
  tone?: "paper" | "ink";
  className?: string;
}) {
  const mute = tone === "ink" ? "on-ink-mute" : "on-paper-mute";
  return (
    <div className={cn("max-w-2xl", className)}>
      <p className="kicker t-accent">{kicker}</p>
      <h2 className="display-face mt-4 text-[clamp(2rem,4.4vw,3.15rem)]">{title}</h2>
      {lede && <p className={cn("mt-5 text-pretty text-[16.5px] leading-relaxed", mute)}>{lede}</p>}
    </div>
  );
}
