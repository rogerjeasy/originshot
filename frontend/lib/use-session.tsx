"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";

import { apiFetch } from "./api";
import type { CreditSummary, Me } from "./types";
import { useAuth } from "@/components/auth-provider";

/**
 * Session profile: the backend's view of the signed-in user (roles) plus their credit
 * position. Held in one context rather than fetched per-component because three separate
 * places need it at once — the sidebar (is this an admin?), the header (balance pill), and
 * the generate panel (can they afford this run?) — and each of them mounting its own
 * `/api/me` + `/api/credits` pair would triple the request count on every navigation.
 *
 * `refreshCredits` is exposed so a finished generation can pull the settled balance without
 * a full reload; the balance changes as a *result* of user action, so nothing here polls.
 */
interface SessionValue {
  me: Me | null;
  credits: CreditSummary | null;
  isAdmin: boolean;
  loading: boolean;
  refresh(): Promise<void>;
  refreshCredits(): Promise<void>;
}

const SessionContext = createContext<SessionValue | null>(null);

export function SessionProvider({ children }: { children: ReactNode }) {
  const { user } = useAuth();
  const [me, setMe] = useState<Me | null>(null);
  const [credits, setCredits] = useState<CreditSummary | null>(null);
  const [loading, setLoading] = useState(true);

  const refreshCredits = useCallback(async () => {
    try {
      setCredits(await apiFetch<CreditSummary>("/api/credits"));
    } catch {
      /* leave the last known balance rather than blanking the pill on a transient error */
    }
  }, []);

  const refresh = useCallback(async () => {
    if (!user) {
      setMe(null);
      setCredits(null);
      setLoading(false);
      return;
    }
    setLoading(true);
    try {
      const [profile] = await Promise.all([apiFetch<Me>("/api/me"), refreshCredits()]);
      setMe(profile);
    } catch {
      setMe(null);
    } finally {
      setLoading(false);
    }
  }, [user, refreshCredits]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const value = useMemo<SessionValue>(
    () => ({
      me,
      credits,
      // Authorization is enforced server-side on every /api/admin route; this only decides
      // whether the nav entry is worth rendering.
      isAdmin: Boolean(me?.roles?.includes("admin")),
      loading,
      refresh,
      refreshCredits,
    }),
    [me, credits, loading, refresh, refreshCredits],
  );

  return <SessionContext.Provider value={value}>{children}</SessionContext.Provider>;
}

export function useSession(): SessionValue {
  const ctx = useContext(SessionContext);
  if (!ctx) throw new Error("useSession must be used within SessionProvider");
  return ctx;
}
