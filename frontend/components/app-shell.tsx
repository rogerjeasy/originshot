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
        <Loader2 className="size-6 animate-spin text-muted-foreground" />
      </div>
    );
  }

  return (
    <div className="min-h-dvh">
      {/* Sidebar — icon rail (md) → labelled (lg) */}
      <aside className="fixed inset-y-0 start-0 z-20 hidden w-16 flex-col border-e bg-card md:flex lg:w-60">
        <div className="flex h-14 items-center px-3 lg:px-5">
          <BrandMark wordmarkClassName="hidden lg:inline" />
        </div>
        <nav className="flex flex-1 flex-col gap-1 p-2 lg:p-3">
          {nav.map(({ href, label, icon: Icon }) => {
            const active = pathname.startsWith(href);
            return (
              <Link
                key={href}
                href={href}
                className={cn(
                  "flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors",
                  active
                    ? "bg-secondary text-foreground"
                    : "text-muted-foreground hover:bg-secondary hover:text-foreground",
                )}
                title={label}
              >
                <Icon className="size-5 shrink-0" />
                <span className="hidden lg:inline">{label}</span>
              </Link>
            );
          })}
        </nav>
      </aside>

      <div className="flex min-h-dvh flex-col md:ps-16 lg:ps-60">
        <header className="sticky top-0 z-10 flex h-14 items-center justify-between gap-3 border-b bg-background/85 px-4 backdrop-blur sm:px-6">
          <span className="min-w-0 truncate font-mono text-xs text-muted-foreground">
            {user.email}
          </span>
          <div className="flex items-center gap-2">
            <CreditsPill />
            <ThemeToggle />
            <Button variant="ghost" size="sm" onClick={() => void signOut()}>
              <LogOut /> Sign out
            </Button>
          </div>
        </header>

        <main className="mx-auto w-full max-w-7xl flex-1 px-4 py-6 pb-24 sm:px-6 md:pb-8 lg:px-8">
          {children}
        </main>
      </div>

      {/* Bottom nav (mobile) */}
      <nav
        className={cn(
          "fixed inset-x-0 bottom-0 z-20 grid border-t bg-card md:hidden",
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
              className={cn(
                "flex flex-col items-center gap-1 py-2 text-xs",
                active ? "text-accent" : "text-muted-foreground",
              )}
            >
              <Icon className="size-5" />
              {label}
            </Link>
          );
        })}
      </nav>
    </div>
  );
}
