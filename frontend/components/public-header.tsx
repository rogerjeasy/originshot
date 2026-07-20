import Link from "next/link";
import type { ReactNode } from "react";

import { BrandMark } from "./brand-mark";
import { buttonVariants } from "./ui/button";

/**
 * Header for public (signed-out) pages. The right-hand `actions` slot is injectable so
 * each page chooses its own CTAs without this component knowing about them.
 *
 * `tone="ink"` matches the header to a page sitting on the ink ground: the bar
 * goes transparent so the viewing light behind it is uninterrupted, and the
 * hairline moves to the ink family. Without it the default `bg-background` bar
 * would sit as a pale strip across the top of a dark page.
 *
 * No theme toggle: the public surface is committed to the ink viewing room, so
 * offering a light/dark switch would only have promised something these pages
 * no longer honour. The theme class is still set from the system preference
 * before paint, and the app's own surfaces still follow it.
 */
export function PublicHeader({
  actions,
  tone = "default",
}: {
  actions?: ReactNode;
  tone?: "default" | "ink";
}) {
  const ink = tone === "ink";
  return (
    <header
      className={
        ink
          ? "relative z-10 border-b"
          : "sticky top-0 z-10 border-b bg-background/85 backdrop-blur"
      }
      style={ink ? { borderColor: "var(--ink-line)" } : undefined}
    >
      <div className="mx-auto flex max-w-7xl items-center justify-between px-4 py-3 sm:px-6 lg:px-8">
        <BrandMark href="/" />
        <div className="flex items-center gap-2">
          {actions ?? (
            <Link
              href="/studio"
              className={
                ink
                  ? "btn-tungsten inline-flex h-9 items-center rounded-lg px-4 text-[13.5px] font-semibold"
                  : buttonVariants({ variant: "accent", size: "sm" })
              }
            >
              Open the Studio
            </Link>
          )}
        </div>
      </div>
    </header>
  );
}
