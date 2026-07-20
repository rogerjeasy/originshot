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
 *
 * `ground="ink"` puts the signed-out view in the viewing room, matching /signin.
 * It applies only when signed out: inside the app shell the content area sits
 * next to a themed sidebar, and a permanently dark panel there would read as a
 * rendering fault rather than a choice. A public visitor gets the room; a
 * signed-in user gets their app.
 */
export function AdaptiveChrome({
  children,
  ground = "app",
}: {
  children: ReactNode;
  ground?: "app" | "ink";
}) {
  const { user, loading } = useAuth();

  if (loading) {
    return (
      <div
        className={`grid min-h-dvh place-items-center ${ground === "ink" ? "ink-ground" : ""}`}
      >
        <Loader2 className="size-6 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (user) return <AppShell>{children}</AppShell>;

  if (ground === "ink") {
    return (
      <div className="ink-ground viewing-light relative min-h-dvh overflow-hidden">
        <PublicHeader tone="ink" />
        <main className="relative min-h-[calc(100dvh-57px)]">{children}</main>
      </div>
    );
  }

  return (
    <div className="min-h-dvh">
      <PublicHeader />
      <main className="min-h-[calc(100dvh-57px)]">{children}</main>
    </div>
  );
}
