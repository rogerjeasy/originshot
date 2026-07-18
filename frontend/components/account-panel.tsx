"use client";

import { LogOut } from "lucide-react";

import { useSession } from "@/lib/use-session";
import { useAuth } from "./auth-provider";
import { Badge } from "./ui/badge";
import { Button } from "./ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "./ui/card";
import { Skeleton } from "./ui/skeleton";

function formatDate(iso?: string | null): string {
  if (!iso) return "—";
  const d = new Date(iso);
  return Number.isNaN(d.getTime())
    ? "—"
    : d.toLocaleDateString(undefined, { month: "long", year: "numeric" });
}

/**
 * Who you're signed in as.
 *
 * Sign-out is also in the sidebar rail; it's repeated here deliberately, because
 * Settings is where people go looking for it and the rail collapses to icons
 * below lg.
 */
export function AccountPanel() {
  const { me, loading } = useSession();
  const { signOut } = useAuth();

  return (
    <Card>
      <CardHeader>
        <CardTitle>Account</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        {loading && !me ? (
          <div className="space-y-2">
            <Skeleton className="h-4 w-40" />
            <Skeleton className="h-3 w-24" />
          </div>
        ) : !me ? (
          <p className="text-sm text-muted-foreground">Not signed in.</p>
        ) : (
          <>
            <dl className="space-y-3 text-sm">
              <div className="flex flex-col gap-0.5">
                <dt className="label text-muted-foreground">Email</dt>
                <dd className="truncate font-mono text-xs" title={me.email ?? undefined}>
                  {me.email ?? "—"}
                </dd>
              </div>

              {me.username && (
                <div className="flex flex-col gap-0.5">
                  <dt className="label text-muted-foreground">Username</dt>
                  <dd className="truncate">{me.username}</dd>
                </div>
              )}

              <div className="flex flex-col gap-1">
                <dt className="label text-muted-foreground">Roles</dt>
                <dd className="flex flex-wrap gap-1.5">
                  {me.roles.length > 0 ? (
                    me.roles.map((r) => (
                      <Badge key={r} variant={r === "admin" ? "accent" : "outline"} size="sm">
                        {r}
                      </Badge>
                    ))
                  ) : (
                    <span className="text-muted-foreground">—</span>
                  )}
                </dd>
              </div>

              <div className="flex flex-col gap-0.5">
                <dt className="label text-muted-foreground">Member since</dt>
                <dd>{formatDate(me.created_at)}</dd>
              </div>
            </dl>

            <Button
              variant="outline"
              size="sm"
              className="w-full"
              onClick={() => void signOut()}
            >
              <LogOut /> Sign out
            </Button>
          </>
        )}
      </CardContent>
    </Card>
  );
}
