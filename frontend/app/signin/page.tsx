"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { ArrowRight, Database, Loader2, Lock, ShieldCheck, Sparkles } from "lucide-react";

import { useAuth } from "@/components/auth-provider";
import { BrandMark } from "@/components/brand-mark";
import { ThemeToggle } from "@/components/theme-toggle";
import { FadeIn } from "@/components/motion/fade-in";
import { Alert } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

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

export default function SignInPage() {
  const { configured, user, signIn, signUp } = useAuth();
  const router = useRouter();
  const [mode, setMode] = useState<"in" | "up">("in");
  const [username, setUsername] = useState("");
  const [email, setEmail] = useState("");
  const [pw, setPw] = useState("");
  const [confirm, setConfirm] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    if (user) router.replace("/studio");
  }, [user, router]);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (mode === "up") {
      if (username.trim().length < 2) return setErr("Username must be at least 2 characters.");
      if (pw.length < 6) return setErr("Password must be at least 6 characters.");
      if (pw !== confirm) return setErr("Passwords do not match.");
    }
    setBusy(true);
    setErr(null);
    try {
      if (mode === "in") await signIn(email, pw);
      else await signUp(email, pw, username.trim());
      router.replace("/studio");
    } catch (e2) {
      setErr(e2 instanceof Error ? e2.message : "Authentication failed");
    } finally {
      setBusy(false);
    }
  }

  function switchMode() {
    setMode(mode === "in" ? "up" : "in");
    setErr(null);
    setConfirm("");
  }

  return (
    <div className="relative min-h-dvh overflow-hidden">
      <div aria-hidden className="bg-grid absolute inset-0 -z-10" />
      <div aria-hidden className="glow-cobalt absolute inset-x-0 top-0 -z-10 h-[440px]" />

      <header className="mx-auto flex max-w-6xl items-center justify-between px-4 py-5 sm:px-6 lg:px-8">
        <BrandMark href="/" />
        <div className="flex items-center gap-2">
          <Link
            href="/how-it-works"
            className="hidden rounded-lg px-3 py-1.5 text-sm font-medium text-muted-foreground transition-colors hover:text-foreground sm:inline-flex"
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
            <Badge variant="verified" className="mb-5 border border-verified/25 bg-verified/10 px-3 py-1">
              <ShieldCheck /> Provenance-verified by design
            </Badge>
            <h1 className="text-balance text-4xl font-semibold leading-[1.1] tracking-tight">
              Your studio,
              <br />
              <span className="text-muted-foreground">signed in.</span>
            </h1>
            <p className="mt-4 max-w-md text-pretty text-muted-foreground">
              Sign in to turn one phone photo into a full, marketplace-ready pack — every asset
              stored and provable, isolated to your account.
            </p>
            <ul className="mt-8 space-y-3">
              {PITCH.map(({ icon: Icon, text }) => (
                <li key={text} className="flex items-start gap-3">
                  <span className="mt-0.5 grid size-7 shrink-0 place-items-center rounded-lg bg-secondary ring-1 ring-border">
                    <Icon className="size-4 text-accent" />
                  </span>
                  <span className="text-sm text-muted-foreground">{text}</span>
                </li>
              ))}
            </ul>
          </FadeIn>

          {/* Auth card */}
          <FadeIn delay={0.1} y={16} className="w-full">
            <Card className="mx-auto w-full max-w-md frame-deep">
              <CardContent className="p-6 sm:p-8">
                {/* compact brand pitch on mobile */}
                <div className="mb-6 lg:hidden">
                  <Badge
                    variant="verified"
                    className="border border-verified/25 bg-verified/10 px-3 py-1"
                  >
                    <ShieldCheck /> Provenance-verified
                  </Badge>
                </div>

                {!configured ? (
                  <div className="space-y-4">
                    <div className="flex items-center gap-3">
                      <span className="grid size-10 place-items-center rounded-xl bg-secondary ring-1 ring-border">
                        <Lock className="size-5" />
                      </span>
                      <div>
                        <h2 className="text-lg font-semibold tracking-tight">Sign-in unavailable</h2>
                        <p className="text-sm text-muted-foreground">Authentication isn&apos;t configured</p>
                      </div>
                    </div>
                    <Alert variant="info">
                      Set your Firebase web config in <span className="font-mono">.env.local</span>{" "}
                      to enable sign-in. There is no dev bypass — auth is always enforced.
                    </Alert>
                    <div className="rounded-lg border bg-muted/50 p-3">
                      <p className="mb-1.5 text-xs font-medium uppercase tracking-wide text-muted-foreground">
                        Required
                      </p>
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
                    <h2 className="text-xl font-semibold tracking-tight">
                      {mode === "in" ? "Welcome back" : "Create your account"}
                    </h2>
                    <p className="mt-1 text-sm text-muted-foreground">
                      {mode === "in"
                        ? "Sign in to open your studio."
                        : "Start turning photos into verified packs."}
                    </p>

                    <form onSubmit={submit} className="mt-6 space-y-4">
                      {mode === "up" && (
                        <div className="space-y-1.5">
                          <Label htmlFor="username">Username</Label>
                          <Input
                            id="username"
                            type="text"
                            autoComplete="username"
                            placeholder="your-handle"
                            value={username}
                            onChange={(e) => setUsername(e.target.value)}
                            required
                            minLength={2}
                            maxLength={40}
                          />
                        </div>
                      )}
                      <div className="space-y-1.5">
                        <Label htmlFor="email">Email</Label>
                        <Input
                          id="email"
                          type="email"
                          autoComplete="email"
                          placeholder="you@store.com"
                          value={email}
                          onChange={(e) => setEmail(e.target.value)}
                          required
                        />
                      </div>
                      <div className="space-y-1.5">
                        <Label htmlFor="pw">Password</Label>
                        <Input
                          id="pw"
                          type="password"
                          autoComplete={mode === "in" ? "current-password" : "new-password"}
                          placeholder="••••••••"
                          value={pw}
                          onChange={(e) => setPw(e.target.value)}
                          required
                          minLength={mode === "up" ? 6 : undefined}
                        />
                      </div>
                      {mode === "up" && (
                        <div className="space-y-1.5">
                          <Label htmlFor="confirm">Confirm password</Label>
                          <Input
                            id="confirm"
                            type="password"
                            autoComplete="new-password"
                            placeholder="••••••••"
                            value={confirm}
                            onChange={(e) => setConfirm(e.target.value)}
                            required
                            minLength={6}
                          />
                        </div>
                      )}

                      {err && <Alert>{err}</Alert>}

                      <Button type="submit" variant="accent" className="w-full" disabled={busy}>
                        {busy ? <Loader2 className="animate-spin" /> : null}
                        {mode === "in" ? "Sign in" : "Create account"}
                      </Button>
                    </form>

                    <div className="mt-5 border-t pt-5 text-center text-sm text-muted-foreground">
                      {mode === "in" ? "New to OriginShot?" : "Already have an account?"}{" "}
                      <button
                        type="button"
                        className="font-medium text-accent hover:underline"
                        onClick={switchMode}
                      >
                        {mode === "in" ? "Create an account" : "Sign in"}
                      </button>
                    </div>
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
