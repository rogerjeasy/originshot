"use client";

import { FileCheck2, ShieldAlert, ShieldCheck, ShieldX, Sparkles } from "lucide-react";

import { shortHash } from "@/lib/utils";
import type { VerifyResult } from "@/lib/types";
import { Card, CardContent } from "./ui/card";

function Row({ label, value, mono }: { label: string; value: string; mono?: boolean }) {
  return (
    <div className="flex items-center justify-between gap-2 border-b pb-1">
      <dt className="shrink-0 text-muted-foreground">{label}</dt>
      <dd className={mono ? "truncate font-mono text-xs" : "truncate"}>{value}</dd>
    </div>
  );
}

export function VerifyPanel({ result }: { result: VerifyResult }) {
  const tampered = result.content_bound === false;

  if (!result.found && !result.embedded) {
    return (
      <Card>
        <CardContent className="flex items-center gap-3 pt-5">
          <ShieldX className="size-6 shrink-0 text-warning" />
          <div className="min-w-0">
            <p className="font-medium">No record found</p>
            <p className="break-all font-mono text-xs text-muted-foreground">{result.sha256}</p>
          </div>
        </CardContent>
      </Card>
    );
  }

  const auth = result.is_authentic;
  return (
    <Card>
      <CardContent className="space-y-4 pt-5">
        <div className="flex items-center gap-3">
          <span
            className="grid size-10 shrink-0 place-items-center rounded-xl"
            style={{
              backgroundColor: tampered
                ? "color-mix(in srgb, var(--color-danger) 14%, transparent)"
                : "color-mix(in srgb, var(--color-verified) 14%, transparent)",
            }}
          >
            {tampered ? (
              <ShieldAlert className="size-5 text-danger" />
            ) : auth ? (
              <ShieldCheck className="size-5 text-verified" />
            ) : (
              <Sparkles className="size-5" />
            )}
          </span>
          <div className="min-w-0">
            <p className="font-semibold">
              {tampered ? "Content altered" : result.verified ? "Integrity verified" : "Unverified"}
            </p>
            <p className="text-sm text-muted-foreground">
              {auth ? "Authentic original" : "AI-generated"}
            </p>
          </div>
        </div>

        {/* Status pills — icon + text + color, never color alone. */}
        <div className="flex flex-wrap gap-2 text-xs">
          <span
            className="inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 font-medium"
            style={{
              backgroundColor: result.verified
                ? "color-mix(in srgb, var(--color-verified) 12%, transparent)"
                : "color-mix(in srgb, var(--color-warning) 14%, transparent)",
              color: result.verified ? "var(--color-verified)" : "var(--color-warning)",
            }}
          >
            <ShieldCheck className="size-3.5" />
            {result.verified ? "Manifest valid" : "Manifest invalid"}
          </span>

          {result.content_bound === true && (
            <span
              className="inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 font-medium"
              style={{
                backgroundColor: "color-mix(in srgb, var(--color-verified) 12%, transparent)",
                color: "var(--color-verified)",
              }}
            >
              <FileCheck2 className="size-3.5" /> Content-bound
            </span>
          )}
          {tampered && (
            <span
              className="inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 font-medium"
              style={{
                backgroundColor: "color-mix(in srgb, var(--color-danger) 14%, transparent)",
                color: "var(--color-danger)",
              }}
            >
              <ShieldAlert className="size-3.5" /> Tampered
            </span>
          )}
          {result.embedded && (
            <span className="inline-flex items-center gap-1.5 rounded-full bg-secondary px-2.5 py-1 font-medium text-secondary-foreground">
              <Sparkles className="size-3.5" /> Manifest embedded
            </span>
          )}
        </div>

        <dl className="grid grid-cols-1 gap-2 text-sm sm:grid-cols-2">
          <Row label="SHA-256" value={shortHash(result.sha256, 10, 10)} mono />
          {result.provider && <Row label="Provider" value={result.provider} mono />}
          {result.model && <Row label="Model" value={result.model} mono />}
          {result.parent_sha256 && (
            <Row label="Derived from" value={shortHash(result.parent_sha256, 8, 8)} mono />
          )}
          {result.style && <Row label="Style" value={result.style} />}
        </dl>

        <p
          className="rounded-lg p-3 text-sm"
          style={
            tampered
              ? {
                  backgroundColor: "color-mix(in srgb, var(--color-danger) 10%, transparent)",
                  color: "var(--color-danger)",
                }
              : { backgroundColor: "var(--color-muted)", color: "var(--color-muted-foreground)" }
          }
        >
          {result.disclosure}
        </p>
      </CardContent>
    </Card>
  );
}
