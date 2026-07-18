import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";

import { cn } from "@/lib/utils";

/**
 * One key action per screen gets `accent` (ColorChecker patch 13). Everything
 * else is ink or quieter — the signal only means something if it stays rare.
 */
const buttonVariants = cva(
  [
    "inline-flex shrink-0 items-center justify-center gap-2 whitespace-nowrap rounded-md",
    "text-sm font-medium tracking-[-0.006em]",
    "transition-[background-color,color,border-color,box-shadow,transform] duration-150",
    "outline-none disabled:pointer-events-none disabled:opacity-45",
    "active:translate-y-px",
    "[&_svg]:size-4 [&_svg]:shrink-0",
  ].join(" "),
  {
    variants: {
      variant: {
        default: "bg-primary text-primary-foreground shadow-raised hover:bg-primary/88",
        accent: "bg-accent text-accent-foreground shadow-raised hover:bg-accent-hover",
        secondary: "bg-secondary text-secondary-foreground hover:bg-border",
        outline: "border bg-card text-foreground shadow-raised hover:bg-secondary",
        ghost: "text-muted-foreground hover:bg-secondary hover:text-foreground",
        destructive: "bg-danger text-white shadow-raised hover:bg-danger/88",
        link: "text-accent underline decoration-accent/30 underline-offset-4 hover:decoration-accent",
      },
      size: {
        sm: "h-8 gap-1.5 px-2.5 text-[13px]",
        default: "h-10 px-4",
        lg: "h-12 px-6 text-[15px]",
        icon: "size-10",
        "icon-sm": "size-8 [&_svg]:size-3.5",
      },
    },
    defaultVariants: { variant: "default", size: "default" },
  },
);

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {}

const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, ...props }, ref) => (
    <button ref={ref} className={cn(buttonVariants({ variant, size }), className)} {...props} />
  ),
);
Button.displayName = "Button";

export { Button, buttonVariants };
