"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Menu, X } from "lucide-react";

import { cn } from "@/lib/utils";
import { BrandMark } from "@/components/brand-mark";

const NAV = [
  { href: "/how-it-works", label: "How it works" },
  { href: "/check", label: "Check a listing" },
  { href: "/verify", label: "Verify" },
  { href: "/ledger", label: "Transparency log" },
  { href: "/about", label: "About" },
];

/**
 * The landing header sits inside the hero's ink band, so it starts transparent
 * and only takes a surface once the page has scrolled past the hero's top edge.
 * It is separate from MarketingHeader because the other public pages open on a
 * light surface and need the opposite treatment.
 */
export function LandingHeader() {
  const [stuck, setStuck] = useState(false);
  const [open, setOpen] = useState(false);

  useEffect(() => {
    const onScroll = () => setStuck(window.scrollY > 12);
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  return (
    <header
      className={cn(
        "sticky top-0 z-40 transition-colors duration-300",
        stuck && "border-b backdrop-blur-md",
      )}
      style={stuck ? { backgroundColor: "color-mix(in srgb, var(--ink) 88%, transparent)" } : undefined}
    >
      <div className="mx-auto flex max-w-[1320px] items-center justify-between gap-4 px-5 py-4 sm:px-8">
        <BrandMark href="/" />

        <nav className="hidden items-center gap-1 md:flex" aria-label="Main">
          {NAV.map((l) => (
            <Link
              key={l.href}
              href={l.href}
              className="on-ink-mute rounded-md px-3 py-1.5 text-[13.5px] font-medium transition-colors hover:text-[var(--ink-fg)]"
            >
              {l.label}
            </Link>
          ))}
        </nav>

        <div className="flex items-center gap-2">
          <Link
            href="/signin"
            className="on-ink-mute hidden rounded-md px-3 py-1.5 text-[13.5px] font-medium transition-colors hover:text-[var(--ink-fg)] sm:block"
          >
            Sign in
          </Link>
          <Link
            href="/studio"
            className="btn-tungsten hidden h-9 items-center rounded-md px-4 text-[13.5px] font-semibold md:inline-flex"
          >
            Start free
          </Link>
          <button
            type="button"
            className="btn-on-ink grid size-9 place-items-center rounded-md md:hidden"
            aria-expanded={open}
            aria-controls="landing-mobile-nav"
            aria-label={open ? "Close menu" : "Open menu"}
            onClick={() => setOpen((v) => !v)}
          >
            {open ? <X className="size-4" /> : <Menu className="size-4" />}
          </button>
        </div>
      </div>

      {open && (
        <nav
          id="landing-mobile-nav"
          aria-label="Main"
          className="border-t px-5 py-4 md:hidden"
          style={{ backgroundColor: "var(--ink-2)" }}
        >
          <div className="flex flex-col">
            {NAV.map((l) => (
              <Link
                key={l.href}
                href={l.href}
                onClick={() => setOpen(false)}
                className="on-ink-mute rounded-md px-2 py-2.5 text-sm font-medium transition-colors hover:text-[var(--ink-fg)]"
              >
                {l.label}
              </Link>
            ))}
            <div className="mt-3 grid grid-cols-2 gap-2 border-t pt-4">
              <Link
                href="/signin"
                onClick={() => setOpen(false)}
                className="btn-on-ink inline-flex h-10 items-center justify-center rounded-md text-sm font-medium"
              >
                Sign in
              </Link>
              <Link
                href="/studio"
                onClick={() => setOpen(false)}
                className="btn-tungsten inline-flex h-10 items-center justify-center rounded-md text-sm font-semibold"
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
