"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { ArrowLeft, RefreshCw } from "lucide-react";

import { useApiData } from "@/lib/use-api";
import type { VerifyResult } from "@/lib/types";
import { AdaptiveChrome } from "@/components/adaptive-chrome";
import { FadeIn } from "@/components/motion/fade-in";
import { VerifyPanel } from "@/components/verify-panel";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";

/** A 64-char hex digest. Anything else never reaches the API. */
const SHA256 = /^[a-f0-9]{64}$/i;

export default function VerifyResultPage() {
  const { sha } = useParams<{ sha: string }>();
  const valid = SHA256.test(sha ?? "");
  const { data, loading, error, reload } = useApiData<VerifyResult>(
    valid ? `/api/verify/${sha}` : null,
  );

  return (
    <AdaptiveChrome>
      <div className="mx-auto max-w-2xl px-4 py-10 sm:px-6">
        <Link
          href="/verify"
          className="mb-5 inline-flex items-center gap-1.5 text-sm text-muted-foreground transition-colors hover:text-foreground"
        >
          <ArrowLeft className="size-4" /> Verify another
        </Link>

        <p className="label mb-2 text-muted-foreground">Provenance record</p>
        <p className="mb-6 break-all font-mono text-xs text-muted-foreground">{sha}</p>

        {!valid ? (
          <Alert variant="warning" title="That doesn't look like a SHA-256">
            A hash is 64 hexadecimal characters. Check the value and try again.
          </Alert>
        ) : loading ? (
          <div className="space-y-3">
            <Skeleton className="h-20 rounded-lg" />
            <Skeleton className="h-44 rounded-lg" />
          </div>
        ) : error ? (
          // Previously this branch rendered nothing at all — on a cold backend the
          // page every marketing hash links to came up blank.
          <Alert
            title="Couldn't reach the provenance ledger"
            action={
              <Button variant="outline" size="sm" onClick={() => void reload()}>
                <RefreshCw /> Retry
              </Button>
            }
          >
            {/* A bare "Failed to fetch" reads as broken. On a cold host that's
                exactly what a first request looks like, so say so. */}
            {/failed to fetch|networkerror|load failed/i.test(error)
              ? "The service may be waking up — a first request can take up to a minute. Try again in a moment."
              : error}
          </Alert>
        ) : data ? (
          <FadeIn>
            <VerifyPanel result={data} />
          </FadeIn>
        ) : null}
      </div>
    </AdaptiveChrome>
  );
}
