import { AlertTriangle, Info, ShieldAlert } from "lucide-react";
import type { LucideIcon } from "lucide-react";

import { cn } from "@/lib/utils";

type Variant = "danger" | "warning" | "info";

const STYLES: Record<Variant, { color: string; icon: LucideIcon }> = {
  danger: { color: "var(--color-danger)", icon: ShieldAlert },
  warning: { color: "var(--color-warning)", icon: AlertTriangle },
  info: { color: "var(--color-info)", icon: Info },
};

/** Calm inline feedback banner — icon + text + color (never color alone). */
export function Alert({
  variant = "danger",
  children,
  className,
}: {
  variant?: Variant;
  children: React.ReactNode;
  className?: string;
}) {
  const { color, icon: Icon } = STYLES[variant];
  return (
    <div
      role="alert"
      className={cn("flex items-start gap-2.5 rounded-lg border p-3 text-sm", className)}
      style={{
        color,
        borderColor: `color-mix(in srgb, ${color} 30%, transparent)`,
        backgroundColor: `color-mix(in srgb, ${color} 8%, transparent)`,
      }}
    >
      <Icon className="mt-0.5 size-4 shrink-0" />
      <div className="min-w-0">{children}</div>
    </div>
  );
}
