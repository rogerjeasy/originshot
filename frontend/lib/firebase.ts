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

/** Current user's ID token, or null when signed out / not configured. */
export async function getIdToken(): Promise<string | null> {
  const a = getFirebaseAuth();
  const user = a?.currentUser;
  return user ? user.getIdToken() : null;
}
