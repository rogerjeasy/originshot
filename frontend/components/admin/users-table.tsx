"use client";

import { useState } from "react";
import { Loader2, Plus } from "lucide-react";

import { apiFetch } from "@/lib/api";
import { cn } from "@/lib/utils";
import type { AdminUserRow } from "@/lib/types";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

const QUICK_GRANTS = [5, 10, 25];

/**
 * Per-user credit position with inline top-up.
 *
 * Grants are attributed to the acting admin server-side and land in the ledger, so this is
 * an auditable action rather than a silent balance edit.
 */
export function UsersTable({
  users,
  onChanged,
}: {
  users: AdminUserRow[];
  onChanged: () => void;
}) {
  const [busyUid, setBusyUid] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function grant(uid: string, amount: number) {
    setBusyUid(uid);
    setError(null);
    try {
      await apiFetch(`/api/admin/users/${uid}/credits`, {
        method: "POST",
        body: JSON.stringify({ amount_usd: amount, note: `Admin top-up $${amount}` }),
      });
      onChanged();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Grant failed");
    } finally {
      setBusyUid(null);
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Users</CardTitle>
      </CardHeader>
      <CardContent>
        {error && <p className="mb-3 text-sm text-danger">{error}</p>}

        {/* Wide table scrolls inside its own container so the page never scrolls sideways. */}
        <div className="-mx-5 overflow-x-auto px-5">
          <table className="w-full min-w-[46rem] text-sm">
            <thead>
              <tr className="border-b text-left text-xs uppercase tracking-wide text-muted-foreground">
                <th className="pb-2 pe-3 font-medium">User</th>
                <th className="pb-2 pe-3 font-medium">Roles</th>
                <th className="pb-2 pe-3 text-right font-medium">SKUs</th>
                <th className="pb-2 pe-3 text-right font-medium">Assets</th>
                <th className="pb-2 pe-3 text-right font-medium">Jobs</th>
                <th className="pb-2 pe-3 text-right font-medium">Spent</th>
                <th className="pb-2 pe-3 text-right font-medium">Balance</th>
                <th className="pb-2 text-right font-medium">Top up</th>
              </tr>
            </thead>
            <tbody className="divide-y">
              {users.map((u) => (
                <tr key={u.uid}>
                  <td className="max-w-[14rem] py-2.5 pe-3">
                    <p className="truncate font-medium">{u.username ?? "—"}</p>
                    <p className="truncate font-mono text-xs text-muted-foreground">
                      {u.email ?? u.uid}
                    </p>
                  </td>
                  <td className="py-2.5 pe-3">
                    <div className="flex flex-wrap gap-1">
                      {u.roles.map((r) => (
                        <span
                          key={r}
                          className={cn(
                            "rounded-full px-2 py-0.5 text-xs",
                            r === "admin"
                              ? "bg-accent/12 t-accent"
                              : "bg-secondary text-secondary-foreground",
                          )}
                        >
                          {r}
                        </span>
                      ))}
                    </div>
                  </td>
                  <td className="tabular py-2.5 pe-3 text-right font-mono">{u.skus}</td>
                  <td className="tabular py-2.5 pe-3 text-right font-mono">{u.assets}</td>
                  <td className="tabular py-2.5 pe-3 text-right font-mono">{u.jobs}</td>
                  <td className="tabular py-2.5 pe-3 text-right font-mono text-muted-foreground">
                    ${u.credits_spent_total.toFixed(2)}
                  </td>
                  <td
                    className={cn(
                      "tabular py-2.5 pe-3 text-right font-mono font-semibold",
                      u.credits_balance < 1 && "text-warning",
                    )}
                  >
                    ${u.credits_balance.toFixed(2)}
                  </td>
                  <td className="py-2.5 text-right">
                    <div className="inline-flex items-center gap-1">
                      {busyUid === u.uid ? (
                        <Loader2 className="size-4 animate-spin text-muted-foreground" />
                      ) : (
                        QUICK_GRANTS.map((amount) => (
                          <Button
                            key={amount}
                            variant="outline"
                            size="sm"
                            className="h-7 px-2 font-mono text-xs"
                            onClick={() => void grant(u.uid, amount)}
                            title={`Grant $${amount} to ${u.email ?? u.uid}`}
                          >
                            <Plus className="size-3" />
                            {amount}
                          </Button>
                        ))
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {users.length === 0 && (
          <p className="py-6 text-center text-sm text-muted-foreground">No users yet.</p>
        )}
      </CardContent>
    </Card>
  );
}
