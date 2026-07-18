import type { LucideIcon } from "lucide-react";
import type { ReactNode } from "react";

import { Card, CardContent } from "./ui/card";

/** Clean framed empty state: icon + guidance + optional primary action. */
export function EmptyState({
  icon: Icon,
  title,
  description,
  action,
}: {
  icon: LucideIcon;
  title: string;
  description?: string;
  action?: ReactNode;
}) {
  return (
    <Card>
      <CardContent className="flex flex-col items-center gap-4 py-14 text-center">
        <span className="grid size-12 place-items-center rounded-2xl bg-secondary text-muted-foreground">
          <Icon className="size-6" />
        </span>
        <div className="max-w-sm">
          <p className="font-medium">{title}</p>
          {description && <p className="mt-1 text-sm text-muted-foreground">{description}</p>}
        </div>
        {action}
      </CardContent>
    </Card>
  );
}
