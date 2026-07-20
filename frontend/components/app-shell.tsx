"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import {
  BarChart3,
  Gauge,
  Images,
  Layers,
  LayoutGrid,
  Loader2,
  LogOut,
  ScrollText,
  Settings,
  ShieldCheck,
  X,
} from "lucide-react";

import { cn } from "@/lib/utils";
import { useSession } from "@/lib/use-session";
import { BrandMark } from "./brand-mark";
import { useAuth } from "./auth-provider";
import { CreditsPill } from "./credits-pill";
import { CommandPalette, type Command } from "./workbench/command-palette";
import { Button } from "./ui/button";
import { TooltipProvider } from "./ui/tooltip";

/**
 * Navigation grouped by intent rather than listed flat.
 *
 * The old rail was six peer links, which made Verify — a thing you do to
 * finished work — sit at the same level as Studio, where work is made. These
 * two verbs are the product: you make things, then you check them. The grouping
 * says so, and Account is the drawer everything else lives in.
 */
const NAV_GROUPS = [
  {
    name: "Create",
    items: [
      { href: "/studio", label: "Studio", icon: LayoutGrid, keywords: "product sku generate new" },
      { href: "/studio/catalog", label: "Catalog Mode", icon: Layers, keywords: "batch bulk many skus folder" },
    ],
  },
  {
    name: "Inspect",
    items: [
      { href: "/library", label: "Library", icon: Images, keywords: "assets photos videos media" },
      { href: "/analytics", label: "Analytics", icon: BarChart3, keywords: "cost spend storage savings providers" },
      { href: "/verify", label: "Verify", icon: ShieldCheck, keywords: "hash provenance check authenticity" },
      { href: "/ledger", label: "Ledger", icon: ScrollText, keywords: "transparency log audit checkpoint" },
    ],
  },
  {
    name: "Account",
    items: [{ href: "/settings", label: "Settings", icon: Settings, keywords: "profile keys billing account" }],
  },
] as const;

// Rendered only for admins. The nav entry is a convenience, not a control: every
// /api/admin route is guarded server-side, so hiding it protects nothing on its own.
const ADMIN_ITEM = { href: "/admin", label: "Admin", icon: Gauge, keywords: "operations queue users" };

/** Bottom nav can't express grouping, so it carries the four most-travelled screens. */
const MOBILE_NAV = [
  { href: "/studio", label: "Studio", icon: LayoutGrid },
  { href: "/library", label: "Library", icon: Images },
  { href: "/analytics", label: "Analytics", icon: BarChart3 },
  { href: "/settings", label: "Settings", icon: Settings },
];

/**
 * `/studio` prefix-matches `/studio/catalog`, so a plain startsWith lights both
 * rows at once. Exact-match the parents that have children under them.
 */
function isActive(pathname: string, href: string) {
  if (href === "/studio") return pathname === "/studio" || /^\/studio\/(?!catalog)/.test(pathname);
  return pathname === href || pathname.startsWith(`${href}/`);
}

export function AppShell({ children }: { children: React.ReactNode }) {
  const { user, loading, signOut } = useAuth();
  const { isAdmin } = useSession();
  const pathname = usePathname();
  const router = useRouter();
  const [mobileNavOpen, setMobileNavOpen] = useState(false);

  const groups = isAdmin
    ? NAV_GROUPS.map((g) =>
        g.name === "Account" ? { ...g, items: [...g.items, ADMIN_ITEM] } : g,
      )
    : NAV_GROUPS.map((g) => ({ ...g, items: [...g.items] }));

  const commands: Command[] = groups.flatMap((g) =>
    g.items.map((i) => ({
      id: i.href,
      label: i.label,
      group: g.name,
      href: i.href,
      keywords: i.keywords,
      icon: i.icon,
    })),
  );

  // Auth is always enforced — no dev bypass. Redirect to /signin when there's no session.
  useEffect(() => {
    if (!loading && !user) router.replace("/signin");
  }, [loading, user, router]);

  // A route change should close the drawer; leaving it open over the new screen
  // is the classic mobile-nav bug.
  useEffect(() => {
    setMobileNavOpen(false);
  }, [pathname]);

  if (loading || !user) {
    return (
      <div className="grid min-h-dvh place-items-center">
        <Loader2 className="size-5 animate-spin text-muted-foreground" />
        <span className="sr-only">Loading your workspace</span>
      </div>
    );
  }

  /**
   * One nav tree, two shapes. The rail collapses to icons below lg; the drawer
   * only ever renders on small screens and has room, so it keeps its labels.
   * Each gets its own accessible name — three landmarks all called "Primary"
   * is indistinguishable noise in a screen reader's landmark list.
   */
  function navTree({ variant }: { variant: "rail" | "drawer" }) {
    const collapsing = variant === "rail";
    return (
      <nav
        className="flex flex-1 flex-col gap-5 overflow-y-auto p-2 lg:p-3"
        aria-label={collapsing ? "Primary" : "All screens"}
      >
        {groups.map((group) => (
          <div key={group.name}>
            {/* A collapsed rail has no room for a heading — the grouping still
                reads as spacing. The drawer shows them. */}
            <p
              className={cn(
                "label mb-1.5 px-3 text-muted-foreground/60",
                collapsing && "max-lg:hidden",
              )}
            >
              {group.name}
            </p>
            <div className="flex flex-col gap-0.5">
              {group.items.map(({ href, label, icon: Icon }) => {
                const active = isActive(pathname, href);
                return (
                  <Link
                    key={href}
                    href={href}
                    aria-current={active ? "page" : undefined}
                    // The rail collapses the label away below lg, so the accessible
                    // name has to come from the element itself, not the visible text.
                    aria-label={label}
                    title={label}
                    className={cn(
                      "relative flex h-10 items-center gap-3 rounded-md px-3 text-sm font-medium transition-colors",
                      collapsing ? "justify-center lg:justify-start" : "justify-start",
                      active
                        ? "bg-secondary text-foreground"
                        : "text-muted-foreground hover:bg-secondary/70 hover:text-foreground",
                    )}
                  >
                    {/* The registration tick: the screen you're on is the plate in register. */}
                    {active && (
                      <span
                        aria-hidden
                        className={cn(
                          "absolute top-1/2 h-5 w-[3px] -translate-y-1/2 rounded-full bg-accent",
                          collapsing ? "-start-2 lg:-start-3" : "-start-1",
                        )}
                      />
                    )}
                    <Icon className="size-[18px] shrink-0" />
                    <span aria-hidden className={cn(collapsing && "hidden lg:inline")}>
                      {label}
                    </span>
                  </Link>
                );
              })}
            </div>
          </div>
        ))}
      </nav>
    );
  }

  function identityFooter({ variant }: { variant: "rail" | "drawer" }) {
    const collapsing = variant === "rail";
    return (
      <div className="border-t p-3">
        <p
          className={cn(
            "label-mono truncate px-1 text-muted-foreground/70",
            collapsing && "max-lg:hidden",
          )}
        >
          {user!.email}
        </p>
        <Button
          variant="ghost"
          size="sm"
          onClick={() => void signOut()}
          className={cn("mt-1.5 w-full", collapsing ? "lg:justify-start max-lg:px-0" : "justify-start")}
          aria-label="Sign out"
        >
          <LogOut />
          <span className={cn(collapsing && "hidden lg:inline")}>Sign out</span>
        </Button>
      </div>
    );
  }

  return (
    <TooltipProvider delayDuration={300}>
      <div className="min-h-dvh">
        {/* Sidebar — icon rail (md) → labelled (lg) */}
        <aside className="fixed inset-y-0 start-0 z-20 hidden w-16 flex-col border-e bg-card md:flex lg:w-[228px]">
          <div className="flex h-14 shrink-0 items-center px-3.5 lg:px-5">
            <BrandMark wordmarkClassName="hidden lg:inline" />
          </div>
          {navTree({ variant: "rail" })}
          {identityFooter({ variant: "rail" })}
        </aside>

        <div className="flex min-h-dvh flex-col md:ps-16 lg:ps-[228px]">
          <header className="sticky top-0 z-10 flex h-14 items-center justify-between gap-3 border-b bg-background/85 px-4 backdrop-blur-md sm:px-6">
            <BrandMark className="md:hidden" wordmarkClassName="sr-only" />
            <div className="flex min-w-0 flex-1 items-center gap-3">
              <CommandPalette commands={commands} />
            </div>
            <div className="flex items-center gap-2">
              <CreditsPill />
            </div>
          </header>

          <main className="mx-auto w-full max-w-[1400px] flex-1 px-4 py-8 pb-24 sm:px-6 md:pb-12 lg:px-8">
            {children}
          </main>
        </div>

        {/* Bottom nav (mobile) */}
        <nav
          aria-label="Primary"
          className="fixed inset-x-0 bottom-0 z-20 grid grid-cols-5 border-t bg-card/95 backdrop-blur-md md:hidden"
          style={{ paddingBottom: "env(safe-area-inset-bottom)" }}
        >
          {MOBILE_NAV.map(({ href, label, icon: Icon }) => {
            const active = isActive(pathname, href);
            return (
              <Link
                key={href}
                href={href}
                aria-current={active ? "page" : undefined}
                className={cn(
                  "flex min-h-[56px] flex-col items-center justify-center gap-1 text-[11px] font-medium transition-colors",
                  active ? "text-foreground" : "text-muted-foreground",
                )}
              >
                <span className="relative">
                  <Icon className="size-[18px]" />
                  {active && (
                    <span
                      aria-hidden
                      className="absolute -top-2 left-1/2 h-[3px] w-4 -translate-x-1/2 rounded-full bg-accent"
                    />
                  )}
                </span>
                {label}
              </Link>
            );
          })}
          {/* Everything the four primary tabs can't hold, including Admin. */}
          <button
            type="button"
            onClick={() => setMobileNavOpen(true)}
            className="flex min-h-[56px] flex-col items-center justify-center gap-1 text-[11px] font-medium text-muted-foreground"
            aria-label="More screens"
          >
            <Layers className="size-[18px]" />
            More
          </button>
        </nav>

        {mobileNavOpen && (
          <div className="fixed inset-0 z-30 md:hidden">
            <button
              type="button"
              aria-label="Close menu"
              onClick={() => setMobileNavOpen(false)}
              className="anim-overlay absolute inset-0 bg-foreground/25 backdrop-blur-[2px]"
            />
            <div className="absolute inset-x-0 bottom-0 max-h-[80dvh] overflow-y-auto rounded-t-xl border-t bg-card pb-[env(safe-area-inset-bottom)]">
              <div className="flex items-center justify-between border-b px-4 py-3">
                <p className="label text-muted-foreground">All screens</p>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => setMobileNavOpen(false)}
                  aria-label="Close menu"
                >
                  <X />
                </Button>
              </div>
              {navTree({ variant: "drawer" })}
              {identityFooter({ variant: "drawer" })}
            </div>
          </div>
        )}
      </div>
    </TooltipProvider>
  );
}
