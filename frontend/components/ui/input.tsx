import * as React from "react";

import { cn } from "@/lib/utils";

const fieldBase = [
  "w-full rounded-md border bg-card text-sm text-foreground",
  "transition-[border-color,box-shadow] duration-150",
  "placeholder:text-muted-foreground/70",
  "hover:border-muted-foreground/40",
  "focus-visible:border-accent focus-visible:outline-none",
  "focus-visible:ring-2 focus-visible:ring-accent/25",
  "disabled:cursor-not-allowed disabled:opacity-50",
  "aria-[invalid=true]:border-danger aria-[invalid=true]:ring-danger/25",
].join(" ");

const Input = React.forwardRef<HTMLInputElement, React.InputHTMLAttributes<HTMLInputElement>>(
  ({ className, type, ...props }, ref) => (
    <input type={type} ref={ref} className={cn(fieldBase, "h-10 px-3", className)} {...props} />
  ),
);
Input.displayName = "Input";

const Textarea = React.forwardRef<
  HTMLTextAreaElement,
  React.TextareaHTMLAttributes<HTMLTextAreaElement>
>(({ className, ...props }, ref) => (
  <textarea ref={ref} className={cn(fieldBase, "min-h-20 px-3 py-2", className)} {...props} />
));
Textarea.displayName = "Textarea";

const Select = React.forwardRef<
  HTMLSelectElement,
  React.SelectHTMLAttributes<HTMLSelectElement>
>(({ className, ...props }, ref) => (
  <select ref={ref} className={cn(fieldBase, "h-10 px-3 pe-8", className)} {...props} />
));
Select.displayName = "Select";

export { Input, Textarea, Select, fieldBase };
