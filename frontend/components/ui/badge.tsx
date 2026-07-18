import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";

import { cn } from "@/lib/utils";

/**
 * Status is always icon + text + colour, never colour alone. Tinted variants
 * pair a patch hue with its own low-chroma surface so they stay legible on
 * both the paper and darkroom grounds.
 */
const badgeVariants = cva(
  "inline-flex items-center gap-1.5 whitespace-nowrap rounded-full border px-2.5 py-0.5 text-xs font-medium [&_svg]:size-3.5 [&_svg]:shrink-0",
  {
    variants: {
      variant: {
        default: "border-transparent bg-primary text-primary-foreground",
        secondary: "border-transparent bg-secondary text-secondary-foreground",
        outline: "border-border text-muted-foreground",
        accent: "border-transparent bg-accent text-accent-foreground",
        verified: "border-verified/25 bg-verified-surface text-verified",
        warning: "border-warning/25 bg-warning-surface text-warning",
        danger: "border-danger/25 bg-danger-surface text-danger",
        info: "border-info/25 bg-info-surface text-info",
      },
      size: {
        default: "text-xs",
        sm: "px-2 py-px text-[11px] [&_svg]:size-3",
      },
    },
    defaultVariants: { variant: "default", size: "default" },
  },
);

export interface BadgeProps
  extends React.HTMLAttributes<HTMLSpanElement>,
    VariantProps<typeof badgeVariants> {}

function Badge({ className, variant, size, ...props }: BadgeProps) {
  return <span className={cn(badgeVariants({ variant, size }), className)} {...props} />;
}

export { Badge, badgeVariants };
