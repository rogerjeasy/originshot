"use client";

import { getApps, initializeApp, type FirebaseApp } from "firebase/app";
import { getAuth, type Auth } from "firebase/auth";

const config = {
  apiKey: process.env.NEXT_PUBLIC_FIREBASE_API_KEY,
  authDomain: process.env.NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN,
  projectId: process.env.NEXT_PUBLIC_FIREBASE_PROJECT_ID,
  appId: process.env.NEXT_PUBLIC_FIREBASE_APP_ID,
};

export function isFirebaseConfigured(): boolean {
  return Boolean(config.apiKey && config.projectId);
}

let app: FirebaseApp | undefined;
let auth: Auth | undefined;

/** Lazily initialize Firebase Auth on the client (no-op until configured). */
export function getFirebaseAuth(): Auth | null {
  if (!isFirebaseConfigured()) return null;
  if (!app) app = getApps()[0] ?? initializeApp(config);
  if (!auth) auth = getAuth(app);
  return auth;
}

/**
 * Current user's ID token, or null when signed out / not configured.
 *
 * Waits for `authStateReady()` before reading `currentUser`. Firebase restores a persisted
 * session asynchronously, so on a cold page load — someone opening /admin or /library
 * directly, rather than navigating there from inside the app — `currentUser` is still null
 * for the first few hundred milliseconds. Reading it immediately sent the page's opening
 * requests out with no Authorization header, and a signed-in user got "Couldn't load the
 * dashboard" from a server that would happily have answered a moment later.
 *
 * `authStateReady()` resolves as soon as the initial state is known (immediately, on every
 * call after the first), so this costs a microtask in the common case and only actually waits
 * during that first-load window. Fixing it here rather than in each caller means every
 * authenticated fetch in the app is covered, not just the one where the race was noticed.
 */
export async function getIdToken(): Promise<string | null> {
  const a = getFirebaseAuth();
  if (!a) return null;
  await a.authStateReady();
  return a.currentUser ? a.currentUser.getIdToken() : null;
}
