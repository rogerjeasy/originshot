"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Wand2 } from "lucide-react";

import { cn } from "@/lib/utils";
import { BrandMark } from "@/components/brand-mark";
import { ThemeToggle } from "@/components/theme-toggle";
import { buttonVariants } from "@/components/ui/button";

const NAV = [
  { href: "/how-it-works", label: "How it works" },
  { href: "/about", label: "About" },
  { href: "/verify", label: "Verify" },
];

/** Sticky header for the public marketing pages (landing, about, how-it-works). */
export function MarketingHeader() {
  const pathname = usePathname();

  return (
    <header className="sticky top-0 z-30 border-b border-border/70 bg-background/80 backdrop-blur-md">
      <div className="mx-auto flex max-w-7xl items-center justify-between gap-4 px-4 py-3 sm:px-6 lg:px-8">
        <BrandMark href="/" />

        <nav className="hidden items-center gap-1 md:flex">
          {NAV.map((l) => {
            const active = pathname === l.href || pathname.startsWith(`${l.href}/`);
            return (
              <Link
                key={l.href}
                href={l.href}
                className={cn(
                  "rounded-lg px-3 py-1.5 text-sm font-medium transition-colors",
                  active
                    ? "bg-secondary text-foreground"
                    : "text-muted-foreground hover:bg-secondary hover:text-foreground",
                )}
              >
                {l.label}
              </Link>
            );
          })}
        </nav>

        <div className="flex items-center gap-2">
          <Link
            href="/signin"
            className={cn(buttonVariants({ variant: "ghost", size: "sm" }), "hidden sm:inline-flex")}
          >
            Sign in
          </Link>
          <Link href="/studio" className={buttonVariants({ variant: "accent", size: "sm" })}>
            <Wand2 /> Start free
          </Link>
          <ThemeToggle />
        </div>
      </div>
    </header>
  );
}
