"use client";

import { motion, useReducedMotion } from "framer-motion";

/** Gentle on-mount reveal: fade (+ small rise). Opacity-only under reduced motion. */
export function FadeIn({
  children,
  delay = 0,
  y = 8,
  className,
}: {
  children: React.ReactNode;
  delay?: number;
  y?: number;
  className?: string;
}) {
  const reduce = useReducedMotion();
  return (
    <motion.div
      className={className}
      initial={reduce ? { opacity: 0 } : { opacity: 0, y }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.22, ease: "easeOut", delay }}
    >
      {children}
    </motion.div>
  );
}
