"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { ArrowLeft } from "lucide-react";

import { useApiData } from "@/lib/use-api";
import type { VerifyResult } from "@/lib/types";
import { AdaptiveChrome } from "@/components/adaptive-chrome";
import { FadeIn } from "@/components/motion/fade-in";
import { VerifyPanel } from "@/components/verify-panel";

export default function VerifyResultPage() {
  const { sha } = useParams<{ sha: string }>();
  const { data, loading } = useApiData<VerifyResult>(`/api/verify/${sha}`);

  return (
    <AdaptiveChrome>
      <div className="mx-auto max-w-xl px-4 py-10 sm:px-6">
        <Link
          href="/verify"
          className="mb-4 inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
        >
          <ArrowLeft className="size-4" /> Verify another
        </Link>
        {loading ? (
          <div className="shimmer frame h-48 rounded-xl border bg-muted" />
        ) : data ? (
          <FadeIn>
            <VerifyPanel result={data} />
          </FadeIn>
        ) : null}
      </div>
    </AdaptiveChrome>
  );
}
