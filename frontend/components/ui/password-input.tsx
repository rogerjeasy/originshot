"use client";

import * as React from "react";
import { Eye, EyeOff } from "lucide-react";

import { cn } from "@/lib/utils";
import { Input } from "./input";

/**
 * Password field with a reveal toggle.
 *
 * People mistype passwords far more often than they're shoulder-surfed, and a
 * masked field with no way to check the value is the most common cause of a
 * failed sign-in. Defaults to masked; the toggle is keyboard reachable and
 * announces which state it will switch to.
 */
export const PasswordInput = React.forwardRef<
  HTMLInputElement,
  Omit<React.InputHTMLAttributes<HTMLInputElement>, "type">
>(({ className, ...props }, ref) => {
  const [visible, setVisible] = React.useState(false);

  return (
    <div className="relative">
      <Input
        ref={ref}
        type={visible ? "text" : "password"}
        className={cn("pe-10", className)}
        {...props}
      />
      <button
        type="button"
        onClick={() => setVisible((v) => !v)}
        // Not in the tab order: it's a convenience, and stopping between the
        // password field and the submit button on every sign-in is worse.
        tabIndex={-1}
        aria-label={visible ? "Hide password" : "Show password"}
        className="absolute end-1 top-1/2 grid size-8 -translate-y-1/2 place-items-center rounded text-muted-foreground transition-colors hover:text-foreground"
      >
        {visible ? <EyeOff className="size-4" /> : <Eye className="size-4" />}
      </button>
    </div>
  );
});
PasswordInput.displayName = "PasswordInput";
