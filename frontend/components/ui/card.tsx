import * as React from "react";

import { cn } from "@/lib/utils";

/**
 * Panels are mounted objects: hairline border, white ground, minimal elevation.
 * Depth comes from the border doing its job, not from a drop shadow.
 */
function Card({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn(
        "rounded-lg border bg-card text-card-foreground shadow-raised",
        className,
      )}
      {...props}
    />
  );
}

function CardHeader({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("flex flex-col gap-1 p-5", className)} {...props} />;
}

/** Panel titles are micro-labels, not headlines — they name a region, quietly. */
function CardTitle({ className, ...props }: React.HTMLAttributes<HTMLHeadingElement>) {
  return <h3 className={cn("label text-muted-foreground", className)} {...props} />;
}

/** For panels that genuinely lead with a statement rather than a label. */
function CardHeading({ className, ...props }: React.HTMLAttributes<HTMLHeadingElement>) {
  return <h3 className={cn("text-base font-semibold tracking-tight", className)} {...props} />;
}

function CardDescription({ className, ...props }: React.HTMLAttributes<HTMLParagraphElement>) {
  return <p className={cn("text-sm text-muted-foreground", className)} {...props} />;
}

function CardContent({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("p-5 pt-0", className)} {...props} />;
}

function CardFooter({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div className={cn("flex items-center gap-3 border-t bg-muted/40 px-5 py-3", className)} {...props} />
  );
}

export {
  Card,
  CardHeader,
  CardTitle,
  CardHeading,
  CardDescription,
  CardContent,
  CardFooter,
};
