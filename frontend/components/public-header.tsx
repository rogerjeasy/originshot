import Link from "next/link";
import type { ReactNode } from "react";

import { BrandMark } from "./brand-mark";
import { ThemeToggle } from "./theme-toggle";
import { buttonVariants } from "./ui/button";

/**
 * Header for public (signed-out) pages. The right-hand `actions` slot is injectable so
 * each page chooses its own CTAs without this component knowing about them; the theme
 * toggle is always present.
 */
export function PublicHeader({ actions }: { actions?: ReactNode }) {
  return (
    <header className="sticky top-0 z-10 border-b bg-background/85 backdrop-blur">
      <div className="mx-auto flex max-w-7xl items-center justify-between px-4 py-3 sm:px-6 lg:px-8">
        <BrandMark href="/" />
        <div className="flex items-center gap-2">
          {actions ?? (
            <Link href="/studio" className={buttonVariants({ variant: "accent", size: "sm" })}>
              Open the Studio
            </Link>
          )}
          <ThemeToggle />
        </div>
      </div>
    </header>
  );
}
