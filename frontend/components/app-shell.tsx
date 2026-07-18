"use client";

import { useEffect } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import {
  BarChart3,
  Gauge,
  LayoutGrid,
  Loader2,
  LogOut,
  Settings,
  ShieldCheck,
} from "lucide-react";

import { cn } from "@/lib/utils";
import { useSession } from "@/lib/use-session";
import { BrandMark } from "./brand-mark";
import { useAuth } from "./auth-provider";
import { CreditsPill } from "./credits-pill";
import { ThemeToggle } from "./theme-toggle";
import { Button } from "./ui/button";
import { TooltipProvider } from "./ui/tooltip";

const NAV = [
  { href: "/studio", label: "Studio", icon: LayoutGrid },
  { href: "/analytics", label: "Analytics", icon: BarChart3 },
  { href: "/verify", label: "Verify", icon: ShieldCheck },
  { href: "/settings", label: "Settings", icon: Settings },
];

// Rendered only for admins. The nav entry is a convenience, not a control: every
// /api/admin route is guarded server-side, so hiding it protects nothing on its own.
const ADMIN_NAV = { href: "/admin", label: "Admin", icon: Gauge };

export function AppShell({ children }: { children: React.ReactNode }) {
  const { user, loading, signOut } = useAuth();
  const { isAdmin } = useSession();
  const pathname = usePathname();
  const router = useRouter();
  const nav = isAdmin ? [...NAV, ADMIN_NAV] : NAV;

  // Auth is always enforced — no dev bypass. Redirect to /signin when there's no session.
  useEffect(() => {
    if (!loading && !user) router.replace("/signin");
  }, [loading, user, router]);

  if (loading || !user) {
    return (
      <div className="grid min-h-dvh place-items-center">
        <Loader2 className="size-5 animate-spin text-muted-foreground" />
        <span className="sr-only">Loading your workspace</span>
      </div>
    );
  }

  return (
    <TooltipProvider delayDuration={300}>
      <div className="min-h-dvh">
        {/* Sidebar — icon rail (md) → labelled (lg) */}
        <aside className="fixed inset-y-0 start-0 z-20 hidden w-16 flex-col border-e bg-card md:flex lg:w-[228px]">
          <div className="flex h-14 items-center px-3.5 lg:px-5">
            <BrandMark wordmarkClassName="hidden lg:inline" />
          </div>

          <nav className="flex flex-1 flex-col gap-0.5 p-2 lg:p-3" aria-label="Primary">
            {nav.map(({ href, label, icon: Icon }) => {
              const active = pathname.startsWith(href);
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
                    "justify-center lg:justify-start",
                    active
                      ? "bg-secondary text-foreground"
                      : "text-muted-foreground hover:bg-secondary/70 hover:text-foreground",
                  )}
                >
                  {/* Active marker reads as a registration tick against the rail edge. */}
                  {active && (
                    <span
                      aria-hidden
                      className="absolute -start-2 top-1/2 h-5 w-[3px] -translate-y-1/2 rounded-full bg-accent lg:-start-3"
                    />
                  )}
                  <Icon className="size-[18px] shrink-0" />
                  <span aria-hidden className="hidden lg:inline">
                    {label}
                  </span>
                </Link>
              );
            })}
          </nav>

          <div className="border-t p-3">
            <p className="label-mono truncate px-1 text-muted-foreground/70 max-lg:hidden">
              {user.email}
            </p>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => void signOut()}
              className="mt-1.5 w-full lg:justify-start max-lg:px-0"
              aria-label="Sign out"
            >
              <LogOut />
              <span className="hidden lg:inline">Sign out</span>
            </Button>
          </div>
        </aside>

        <div className="flex min-h-dvh flex-col md:ps-16 lg:ps-[228px]">
          <header className="sticky top-0 z-10 flex h-14 items-center justify-between gap-3 border-b bg-background/85 px-4 backdrop-blur-md sm:px-6">
            <BrandMark className="md:hidden" wordmarkClassName="sr-only" />
            <span className="min-w-0 flex-1 truncate font-mono text-xs text-muted-foreground max-md:hidden">
              {user.email}
            </span>
            <div className="flex items-center gap-2">
              <CreditsPill />
              <ThemeToggle />
            </div>
          </header>

          <main className="mx-auto w-full max-w-[1400px] flex-1 px-4 py-6 pb-24 sm:px-6 md:pb-10 lg:px-8">
            {children}
          </main>
        </div>

        {/* Bottom nav (mobile) */}
        <nav
          aria-label="Primary"
          className={cn(
            "fixed inset-x-0 bottom-0 z-20 grid border-t bg-card/95 backdrop-blur-md md:hidden",
            isAdmin ? "grid-cols-5" : "grid-cols-4",
          )}
          style={{ paddingBottom: "env(safe-area-inset-bottom)" }}
        >
          {nav.map(({ href, label, icon: Icon }) => {
            const active = pathname.startsWith(href);
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
        </nav>
      </div>
    </TooltipProvider>
  );
}
