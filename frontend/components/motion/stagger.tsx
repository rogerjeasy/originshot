"use client";

import { motion, useReducedMotion, type Variants } from "framer-motion";

const container: Variants = {
  hidden: {},
  show: { transition: { staggerChildren: 0.05 } },
};

/** Container that staggers its <StaggerItem> children into view (grid "developing" reveal). */
export function Stagger({
  children,
  className,
}: {
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <motion.div className={className} variants={container} initial="hidden" animate="show">
      {children}
    </motion.div>
  );
}

/** A single staggered item: fade + slight scale 0.98→1 (opacity-only under reduced motion). */
export function StaggerItem({
  children,
  className,
}: {
  children: React.ReactNode;
  className?: string;
}) {
  const reduce = useReducedMotion();
  const item: Variants = reduce
    ? { hidden: { opacity: 0 }, show: { opacity: 1 } }
    : { hidden: { opacity: 0, scale: 0.98, y: 8 }, show: { opacity: 1, scale: 1, y: 0 } };
  return (
    <motion.div className={className} variants={item} transition={{ duration: 0.2, ease: "easeOut" }}>
      {children}
    </motion.div>
  );
}
