import { AlertTriangle, CheckCircle2, Info, ShieldAlert } from "lucide-react";
import type { LucideIcon } from "lucide-react";

import { cn } from "@/lib/utils";

type Variant = "danger" | "warning" | "info" | "success";

const STYLES: Record<Variant, { cls: string; icon: LucideIcon }> = {
  danger: { cls: "border-danger/25 bg-danger-surface text-danger", icon: ShieldAlert },
  warning: { cls: "border-warning/25 bg-warning-surface text-warning", icon: AlertTriangle },
  info: { cls: "border-info/25 bg-info-surface text-info", icon: Info },
  success: { cls: "border-verified/25 bg-verified-surface text-verified", icon: CheckCircle2 },
};

/**
 * Inline feedback. States what happened and, where possible, what to do about
 * it — status is icon + text + colour, never colour alone.
 */
export function Alert({
  variant = "danger",
  title,
  children,
  action,
  className,
}: {
  variant?: Variant;
  title?: string;
  children?: React.ReactNode;
  action?: React.ReactNode;
  className?: string;
}) {
  const { cls, icon: Icon } = STYLES[variant];
  return (
    <div
      role="alert"
      className={cn("flex items-start gap-3 rounded-md border p-3 text-sm", cls, className)}
    >
      <Icon className="mt-0.5 size-4 shrink-0" />
      <div className="min-w-0 flex-1">
        {title && <p className="font-medium">{title}</p>}
        {children && <div className={cn("min-w-0", title && "mt-0.5 opacity-90")}>{children}</div>}
      </div>
      {action && <div className="shrink-0">{action}</div>}
    </div>
  );
}
