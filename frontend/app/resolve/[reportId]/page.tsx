"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { ArrowLeft, RefreshCw } from "lucide-react";

import { useApiData } from "@/lib/use-api";
import type { ResolveReport } from "@/lib/types";
import { AdaptiveChrome } from "@/components/adaptive-chrome";
import { FadeIn } from "@/components/motion/fade-in";
import { ResolvePanel } from "@/components/resolve-panel";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";

/**
 * The permalink printed on every Dispute Evidence Report, and the target of its QR code.
 *
 * This is the page a marketplace agent lands on with nothing but the id from a PDF someone
 * forwarded them, so it has to stand alone: no account, no prior context, and a download
 * link for the document itself.
 */
export default function ResolveReportPage() {
  const { reportId } = useParams<{ reportId: string }>();
  const { data, loading, error, reload } = useApiData<ResolveReport>(
    reportId ? `/api/resolve/${reportId}` : null,
  );

  return (
    <AdaptiveChrome>
      <div className="mx-auto max-w-2xl px-4 py-10 sm:px-6">
        <Link
          href="/resolve"
          className="mb-5 inline-flex items-center gap-1.5 text-sm text-muted-foreground transition-colors hover:text-foreground"
        >
          <ArrowLeft className="size-4" /> Run another check
        </Link>

        <p className="label mb-2 text-muted-foreground">Dispute evidence report</p>
        <p className="mb-6 break-all font-mono text-xs text-muted-foreground">{reportId}</p>

        {loading ? (
          <div className="space-y-3">
            <Skeleton className="h-24 rounded-lg" />
            <Skeleton className="h-56 rounded-lg" />
          </div>
        ) : error ? (
          <Alert
            title="Couldn't load that report"
            action={
              <Button variant="outline" size="sm" onClick={() => void reload()}>
                <RefreshCw /> Retry
              </Button>
            }
          >
            {/failed to fetch|networkerror|load failed/i.test(error)
              ? "The service may be waking up — a first request can take up to a minute. Try again in a moment."
              : error}
          </Alert>
        ) : data ? (
          <FadeIn>
            <ResolvePanel report={data} />
          </FadeIn>
        ) : null}
      </div>
    </AdaptiveChrome>
  );
}
