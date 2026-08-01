"use client";

import type { ReactNode } from "react";

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
 *
 * **These pages never block on auth.** They used to render a bare spinner until
 * Firebase resolved `onAuthStateChanged` — which meant /verify and /check, the
 * two surfaces advertised as needing no account, opened on an empty screen while
 * an auth SDK the visitor doesn't need finished loading. The children are
 * identical either way, so the public chrome renders immediately and the shell
 * swaps in only if a user turns out to be signed in. A buyer who never signs in
 * never waits for auth at all; a signed-in user sees the public header for the
 * moment before their session resolves, which is a far cheaper wrong state than
 * a blank page.
 */
export function AdaptiveChrome({
  children,
  ground = "app",
}: {
  children: ReactNode;
  ground?: "app" | "ink";
}) {
  const { user } = useAuth();

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
