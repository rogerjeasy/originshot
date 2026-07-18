"use client";

import {
  createContext,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import {
  createUserWithEmailAndPassword,
  onAuthStateChanged,
  sendPasswordResetEmail,
  signInWithEmailAndPassword,
  signOut as fbSignOut,
  updateProfile,
} from "firebase/auth";

import { apiFetch } from "@/lib/api";
import { getFirebaseAuth, isFirebaseConfigured } from "@/lib/firebase";

/**
 * Persist the signed-in user into the backend `users` collection. Best-effort: a failure
 * here (e.g. a cold backend) must never block sign-in — the record is re-ensured on the
 * next sign-in and lazily by GET /api/me.
 */
async function persistUser(username?: string): Promise<void> {
  try {
    if (username) {
      await apiFetch("/api/users", { method: "POST", body: JSON.stringify({ username }) });
    } else {
      await apiFetch("/api/me"); // ensure a record exists (created with defaults if missing)
    }
  } catch {
    /* non-fatal */
  }
}

export interface AuthUser {
  uid: string;
  email: string | null;
}

interface AuthContextValue {
  user: AuthUser | null;
  loading: boolean;
  configured: boolean;
  signIn(email: string, password: string): Promise<void>;
  signUp(email: string, password: string, username: string): Promise<void>;
  signOut(): Promise<void>;
  resetPassword(email: string): Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const configured = isFirebaseConfigured();
  // No dev bypass: a session only exists once Firebase confirms a signed-in user.
  // When Firebase isn't configured there is simply no session (loading resolves immediately).
  const [user, setUser] = useState<AuthUser | null>(null);
  const [loading, setLoading] = useState<boolean>(configured);

  useEffect(() => {
    if (!configured) return;
    const auth = getFirebaseAuth();
    if (!auth) {
      setLoading(false);
      return;
    }
    return onAuthStateChanged(auth, (u) => {
      setUser(u ? { uid: u.uid, email: u.email } : null);
      setLoading(false);
    });
  }, [configured]);

  const value = useMemo<AuthContextValue>(
    () => ({
      user,
      loading,
      configured,
      async signIn(email, password) {
        const auth = getFirebaseAuth();
        if (!auth) throw new Error("Auth is not configured");
        await signInWithEmailAndPassword(auth, email, password);
        await persistUser(); // ensure the backend profile exists
      },
      async signUp(email, password, username) {
        const auth = getFirebaseAuth();
        if (!auth) throw new Error("Auth is not configured");
        const { user: fbUser } = await createUserWithEmailAndPassword(auth, email, password);
        await updateProfile(fbUser, { displayName: username });
        await persistUser(username); // create the users/{uid} record with role "customer"
      },
      async signOut() {
        const auth = getFirebaseAuth();
        if (auth) await fbSignOut(auth);
      },
      async resetPassword(email) {
        const auth = getFirebaseAuth();
        if (!auth) throw new Error("Auth is not configured");
        await sendPasswordResetEmail(auth, email);
      },
    }),
    [user, loading, configured],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
