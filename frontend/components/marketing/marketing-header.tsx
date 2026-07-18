"use client";

import { useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { Menu, X } from "lucide-react";

import { cn } from "@/lib/utils";
import { BrandMark } from "@/components/brand-mark";
import { ThemeToggle } from "@/components/theme-toggle";
import { Button, buttonVariants } from "@/components/ui/button";

const NAV = [
  { href: "/how-it-works", label: "How it works" },
  { href: "/verify", label: "Verify" },
  { href: "/about", label: "About" },
];

/** Sticky header for the public marketing pages. */
export function MarketingHeader() {
  const pathname = usePathname();
  const [open, setOpen] = useState(false);

  return (
    <header className="sticky top-0 z-30 border-b bg-background/85 backdrop-blur-md">
      <div className="mx-auto flex max-w-[1400px] items-center justify-between gap-4 px-4 py-3 sm:px-6 lg:px-8">
        <BrandMark href="/" />

        <nav className="hidden items-center gap-0.5 md:flex" aria-label="Main">
          {NAV.map((l) => {
            const active = pathname === l.href || pathname.startsWith(`${l.href}/`);
            return (
              <Link
                key={l.href}
                href={l.href}
                aria-current={active ? "page" : undefined}
                className={cn(
                  "rounded-md px-3 py-1.5 text-sm font-medium transition-colors",
                  active
                    ? "text-foreground"
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
          <Link
            href="/studio"
            className={cn(buttonVariants({ variant: "accent", size: "sm" }), "max-md:hidden")}
          >
            Start free
          </Link>
          <ThemeToggle />
          <Button
            variant="ghost"
            size="icon-sm"
            className="md:hidden"
            aria-expanded={open}
            aria-controls="marketing-mobile-nav"
            aria-label={open ? "Close menu" : "Open menu"}
            onClick={() => setOpen((v) => !v)}
          >
            {open ? <X /> : <Menu />}
          </Button>
        </div>
      </div>

      {open && (
        <nav
          id="marketing-mobile-nav"
          aria-label="Main"
          className="border-t bg-card px-4 py-3 md:hidden"
        >
          <div className="flex flex-col gap-0.5">
            {NAV.map((l) => (
              <Link
                key={l.href}
                href={l.href}
                onClick={() => setOpen(false)}
                className="rounded-md px-3 py-2.5 text-sm font-medium text-muted-foreground transition-colors hover:bg-secondary hover:text-foreground"
              >
                {l.label}
              </Link>
            ))}
            <div className="mt-2 grid grid-cols-2 gap-2 border-t pt-3">
              <Link
                href="/signin"
                onClick={() => setOpen(false)}
                className={buttonVariants({ variant: "outline", size: "sm" })}
              >
                Sign in
              </Link>
              <Link
                href="/studio"
                onClick={() => setOpen(false)}
                className={buttonVariants({ variant: "accent", size: "sm" })}
              >
                Start free
              </Link>
            </div>
          </div>
        </nav>
      )}
    </header>
  );
}
