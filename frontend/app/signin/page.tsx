"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { ArrowRight, Database, Loader2, Lock, ShieldCheck, Sparkles } from "lucide-react";

import { authError, type AuthField } from "@/lib/auth-errors";
import { useAuth } from "@/components/auth-provider";
import { BrandMark } from "@/components/brand-mark";
import { ThemeToggle } from "@/components/theme-toggle";
import { FadeIn } from "@/components/motion/fade-in";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Field } from "@/components/ui/label";
import { PasswordInput } from "@/components/ui/password-input";

const PITCH = [
  { icon: Sparkles, text: "One photo in — studio, lifestyle, variants, and video out." },
  { icon: ShieldCheck, text: "Every asset verifiable from its own bytes — provenance by design." },
  { icon: Database, text: "Stored durably on Backblaze B2, isolated to your account." },
];

const FIREBASE_ENV = [
  "NEXT_PUBLIC_FIREBASE_API_KEY",
  "NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN",
  "NEXT_PUBLIC_FIREBASE_PROJECT_ID",
  "NEXT_PUBLIC_FIREBASE_APP_ID",
];

type Mode = "in" | "up" | "reset";

const COPY: Record<Mode, { title: string; sub: string; cta: string }> = {
  in: { title: "Welcome back", sub: "Sign in to open your studio.", cta: "Sign in" },
  up: {
    title: "Create your account",
    sub: "Start turning photos into verified packs.",
    cta: "Create account",
  },
  reset: {
    title: "Reset your password",
    sub: "We'll email you a link to set a new one.",
    cta: "Send reset link",
  },
};

export default function SignInPage() {
  const { configured, user, signIn, signUp, resetPassword } = useAuth();
  const router = useRouter();
  const [mode, setMode] = useState<Mode>("in");
  const [username, setUsername] = useState("");
  const [email, setEmail] = useState("");
  const [pw, setPw] = useState("");
  const [confirm, setConfirm] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [errField, setErrField] = useState<AuthField>(null);
  const [sent, setSent] = useState(false);

  useEffect(() => {
    if (user) router.replace("/studio");
  }, [user, router]);

  function fail(message: string, field: AuthField = null) {
    setErr(message);
    setErrField(field);
  }

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setErr(null);
    setErrField(null);

    if (mode === "up") {
      if (username.trim().length < 2) return fail("Use at least 2 characters.", "username");
      if (pw.length < 6) return fail("Use at least 6 characters.", "password");
      if (pw !== confirm) return fail("Both passwords must match.", "password");
    }

    setBusy(true);
    try {
      if (mode === "in") {
        await signIn(email, pw);
        router.replace("/studio");
      } else if (mode === "up") {
        await signUp(email, pw, username.trim());
        router.replace("/studio");
      } else {
        await resetPassword(email.trim());
        setSent(true);
      }
    } catch (e2) {
      // Firebase's own message names our vendor and not the user's problem.
      const { message, field } = authError(e2);
      fail(message, field);
    } finally {
      setBusy(false);
    }
  }

  function go(next: Mode) {
    setMode(next);
    setErr(null);
    setErrField(null);
    setConfirm("");
    setSent(false);
  }

  const copy = COPY[mode];
  // Field-level errors render under their field; anything unattributable is a banner.
  const banner = err && errField === null ? err : null;
  const fieldErr = (f: AuthField) => (errField === f ? err : null);

  return (
    <div className="relative min-h-dvh overflow-hidden">
      <div aria-hidden className="patch-grid patch-grid-fade absolute inset-0 -z-10" />

      <header className="mx-auto flex max-w-6xl items-center justify-between px-4 py-5 sm:px-6 lg:px-8">
        <BrandMark href="/" />
        <div className="flex items-center gap-2">
          <Link
            href="/how-it-works"
            className="hidden rounded-md px-3 py-1.5 text-sm font-medium text-muted-foreground transition-colors hover:text-foreground sm:inline-flex"
          >
            How it works
          </Link>
          <ThemeToggle />
        </div>
      </header>

      <main className="mx-auto flex min-h-[calc(100dvh-73px)] max-w-6xl items-center px-4 pb-16 sm:px-6 lg:px-8">
        <div className="grid w-full items-center gap-12 lg:grid-cols-2">
          {/* Brand pitch — large screens only */}
          <FadeIn className="hidden lg:block">
            <p className="label text-muted-foreground">Product photography, calibrated</p>
            <h1 className="mt-4 text-balance text-4xl font-semibold leading-[1.1] tracking-[-0.03em]">
              Your studio,
              <br />
              <span className="text-muted-foreground">signed in.</span>
            </h1>
            <p className="mt-5 max-w-md text-pretty text-muted-foreground">
              Turn one phone photo into a full, marketplace-ready pack — every asset stored and
              provable, isolated to your account.
            </p>
            <ul className="mt-8 space-y-3.5">
              {PITCH.map(({ icon: Icon, text }) => (
                <li key={text} className="flex items-start gap-3">
                  <span className="mt-0.5 grid size-7 shrink-0 place-items-center rounded-md border bg-card text-muted-foreground">
                    <Icon className="size-3.5" />
                  </span>
                  <span className="text-sm text-muted-foreground">{text}</span>
                </li>
              ))}
            </ul>
          </FadeIn>

          {/* Auth card */}
          <FadeIn delay={0.1} y={16} className="w-full">
            <Card className="mx-auto w-full max-w-md">
              <CardContent className="p-6 sm:p-8">
                {!configured ? (
                  <div className="space-y-4">
                    <div className="flex items-center gap-3">
                      <span className="grid size-10 shrink-0 place-items-center rounded-md border bg-muted">
                        <Lock className="size-4" />
                      </span>
                      <div className="min-w-0">
                        <h2 className="text-lg font-semibold tracking-tight">
                          Sign-in unavailable
                        </h2>
                        <p className="text-sm text-muted-foreground">
                          Authentication isn&apos;t configured
                        </p>
                      </div>
                    </div>
                    <Alert variant="info">
                      Set your Firebase web config in <span className="font-mono">.env.local</span>{" "}
                      to enable sign-in. There is no dev bypass — auth is always enforced.
                    </Alert>
                    <div className="rounded-md border bg-muted/50 p-3">
                      <p className="label mb-2 text-muted-foreground">Required</p>
                      <ul className="space-y-1">
                        {FIREBASE_ENV.map((k) => (
                          <li key={k} className="truncate font-mono text-xs text-muted-foreground">
                            {k}
                          </li>
                        ))}
                      </ul>
                    </div>
                    <Link
                      href="/"
                      className="inline-flex items-center gap-1 text-sm text-accent hover:underline"
                    >
                      Back to home <ArrowRight className="size-4" />
                    </Link>
                  </div>
                ) : (
                  <>
                    <h2 className="text-xl font-semibold tracking-tight">{copy.title}</h2>
                    <p className="mt-1 text-sm text-muted-foreground">{copy.sub}</p>

                    {sent ? (
                      <div className="mt-6 space-y-4">
                        <Alert variant="success" title="Check your inbox">
                          If an account exists for {email.trim()}, a reset link is on its way.
                        </Alert>
                        <Button variant="outline" className="w-full" onClick={() => go("in")}>
                          Back to sign in
                        </Button>
                      </div>
                    ) : (
                      <>
                        <form onSubmit={submit} className="mt-6 space-y-4" noValidate>
                          {mode === "up" && (
                            <Field
                              htmlFor="username"
                              label="Username"
                              error={fieldErr("username")}
                            >
                              <Input
                                type="text"
                                autoComplete="username"
                                placeholder="your-handle"
                                value={username}
                                onChange={(e) => setUsername(e.target.value)}
                                required
                                minLength={2}
                                maxLength={40}
                              />
                            </Field>
                          )}

                          <Field htmlFor="email" label="Email" error={fieldErr("email")}>
                            <Input
                              type="email"
                              autoComplete="email"
                              placeholder="you@store.com"
                              value={email}
                              onChange={(e) => setEmail(e.target.value)}
                              required
                            />
                          </Field>

                          {mode !== "reset" && (
                            <Field
                              htmlFor="pw"
                              label="Password"
                              error={fieldErr("password")}
                              hint={mode === "up" ? "At least 6 characters" : undefined}
                            >
                              <PasswordInput
                                autoComplete={
                                  mode === "in" ? "current-password" : "new-password"
                                }
                                placeholder="••••••••"
                                value={pw}
                                onChange={(e) => setPw(e.target.value)}
                                required
                              />
                            </Field>
                          )}

                          {mode === "up" && (
                            <Field htmlFor="confirm" label="Confirm password">
                              <PasswordInput
                                autoComplete="new-password"
                                placeholder="••••••••"
                                value={confirm}
                                onChange={(e) => setConfirm(e.target.value)}
                                required
                              />
                            </Field>
                          )}

                          {banner && <Alert>{banner}</Alert>}

                          <Button
                            type="submit"
                            variant="accent"
                            className="w-full"
                            disabled={busy}
                          >
                            {busy && <Loader2 className="animate-spin" />}
                            {copy.cta}
                          </Button>
                        </form>

                        {mode === "in" && (
                          <button
                            type="button"
                            onClick={() => go("reset")}
                            className="mt-3 w-full text-center text-sm text-muted-foreground transition-colors hover:text-foreground"
                          >
                            Forgot your password?
                          </button>
                        )}

                        <div className="mt-5 border-t pt-5 text-center text-sm text-muted-foreground">
                          {mode === "in" ? (
                            <>
                              New to OriginShot?{" "}
                              <button
                                type="button"
                                className="font-medium text-accent hover:underline"
                                onClick={() => go("up")}
                              >
                                Create an account
                              </button>
                            </>
                          ) : (
                            <>
                              Already have an account?{" "}
                              <button
                                type="button"
                                className="font-medium text-accent hover:underline"
                                onClick={() => go("in")}
                              >
                                Sign in
                              </button>
                            </>
                          )}
                        </div>
                      </>
                    )}
                  </>
                )}
              </CardContent>
            </Card>
          </FadeIn>
        </div>
      </main>
    </div>
  );
}
