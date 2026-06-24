import type { ReactNode } from "react";

import { FadeIn } from "@/components/motion/fade-in";

/** Sub-page hero band on the seamless sweep + fading grid + cobalt signal. */
export function MarketingPageHero({
  eyebrow,
  title,
  description,
  children,
}: {
  eyebrow?: string;
  title: string;
  description?: string;
  children?: ReactNode;
}) {
  return (
    <section className="relative overflow-hidden border-b">
      <div aria-hidden className="bg-grid absolute inset-0 -z-10" />
      <div aria-hidden className="glow-cobalt absolute inset-x-0 top-0 -z-10 h-[380px]" />
      <FadeIn className="mx-auto max-w-3xl px-4 py-16 text-center sm:px-6 sm:py-20 lg:px-8">
        {eyebrow && (
          <p className="mb-3 text-sm font-semibold uppercase tracking-wide text-accent">{eyebrow}</p>
        )}
        <h1 className="text-balance text-4xl font-semibold tracking-tight sm:text-5xl">{title}</h1>
        {description && (
          <p className="mx-auto mt-4 max-w-2xl text-pretty text-muted-foreground sm:text-lg">
            {description}
          </p>
        )}
        {children && <div className="mt-8 flex flex-wrap items-center justify-center gap-3">{children}</div>}
      </FadeIn>
    </section>
  );
}
