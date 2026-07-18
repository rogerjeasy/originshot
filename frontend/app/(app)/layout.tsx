"use client";

import { AppShell } from "@/components/app-shell";

/**
 * SessionProvider is deliberately NOT mounted here — it lives in the root
 * layout so public pages that render app chrome (/verify) can read the session
 * too. Re-adding it here would nest a second provider and double every
 * /api/me + /api/credits fetch on navigation.
 */
export default function AppGroupLayout({ children }: { children: React.ReactNode }) {
  return <AppShell>{children}</AppShell>;
}
