"use client";

import { AppShell } from "@/components/app-shell";
import { SessionProvider } from "@/lib/use-session";

export default function AppGroupLayout({ children }: { children: React.ReactNode }) {
  return (
    <SessionProvider>
      <AppShell>{children}</AppShell>
    </SessionProvider>
  );
}
