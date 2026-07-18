/**
 * Firebase auth errors, translated.
 *
 * Raw Firebase messages read like `Firebase: Error (auth/invalid-credential).`
 * — they name our vendor, not the user's problem, and they don't say what to do
 * next. Every message here states what happened and how to fix it.
 *
 * Sign-in failures are deliberately vague about *which* half was wrong: saying
 * "no account with that email" tells an attacker which addresses are registered.
 */

interface FirebaseErrorish {
  code?: unknown;
  message?: unknown;
}

/** The field a failure should be attributed to, so the error lands where the fix is. */
export type AuthField = "email" | "password" | "username" | null;

export interface AuthErrorInfo {
  message: string;
  field: AuthField;
}

const MESSAGES: Record<string, AuthErrorInfo> = {
  // Sign-in — all credential failures give the same answer on purpose.
  "auth/invalid-credential": {
    message: "That email and password don't match. Check both and try again.",
    field: "password",
  },
  "auth/wrong-password": {
    message: "That email and password don't match. Check both and try again.",
    field: "password",
  },
  "auth/user-not-found": {
    message: "That email and password don't match. Check both and try again.",
    field: "password",
  },
  "auth/invalid-email": { message: "Enter a valid email address.", field: "email" },
  "auth/user-disabled": {
    message: "This account has been disabled. Contact support to reopen it.",
    field: null,
  },

  // Sign-up
  "auth/email-already-in-use": {
    message: "An account already uses this email. Sign in instead.",
    field: "email",
  },
  "auth/weak-password": {
    message: "Use at least 6 characters.",
    field: "password",
  },
  "auth/operation-not-allowed": {
    message: "Email sign-in isn't enabled for this project.",
    field: null,
  },

  // Environment
  "auth/too-many-requests": {
    message: "Too many attempts. Wait a few minutes before trying again.",
    field: null,
  },
  "auth/network-request-failed": {
    message: "Couldn't reach the authentication service. Check your connection and try again.",
    field: null,
  },
};

const FALLBACK: AuthErrorInfo = {
  message: "Something went wrong signing you in. Try again in a moment.",
  field: null,
};

export function authError(err: unknown): AuthErrorInfo {
  const code = (err as FirebaseErrorish)?.code;
  if (typeof code === "string" && code in MESSAGES) return MESSAGES[code];

  // Our own provider throws a plain Error for the unconfigured case; pass that
  // through rather than burying it under the generic fallback.
  if (err instanceof Error && err.message === "Auth is not configured") {
    return { message: err.message, field: null };
  }
  return FALLBACK;
}
