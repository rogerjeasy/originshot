"use client";

import type { ReactNode } from "react";
import { Loader2 } from "lucide-react";

import { AppShell } from "./app-shell";
import { useAuth } from "./auth-provider";
import { PublicHeader } from "./public-header";

/**
 * Chrome for pages reachable BOTH inside the app and by signed-out visitors
 * (e.g. /verify, opened from a shared provenance link). Signed-in users get the
 * full app shell with sidebar; signed-out buyers get the lightweight public
 * header — so the page never forces a sign-in just to verify a hash.
 */
export function AdaptiveChrome({ children }: { children: ReactNode }) {
  const { user, loading } = useAuth();

  if (loading) {
    return (
      <div className="grid min-h-dvh place-items-center">
        <Loader2 className="size-6 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (user) return <AppShell>{children}</AppShell>;

  return (
    <div className="min-h-dvh">
      <PublicHeader />
      <main className="min-h-[calc(100dvh-57px)]">{children}</main>
    </div>
  );
}
