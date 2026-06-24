import { cn } from "@/lib/utils";

/** Shared marketing section frame: centered max-width, optional eyebrow + heading. */
export function MarketingSection({
  eyebrow,
  title,
  description,
  className,
  children,
}: {
  eyebrow?: string;
  title?: string;
  description?: string;
  className?: string;
  children: React.ReactNode;
}) {
  return (
    <section className={cn("mx-auto max-w-7xl px-4 py-16 sm:px-6 sm:py-20 lg:px-8", className)}>
      {(eyebrow || title || description) && (
        <div className="mx-auto mb-10 max-w-2xl text-center">
          {eyebrow && (
            <p className="mb-2 text-sm font-semibold uppercase tracking-wide text-accent">
              {eyebrow}
            </p>
          )}
          {title && (
            <h2 className="text-balance text-2xl font-semibold tracking-tight sm:text-3xl">
              {title}
            </h2>
          )}
          {description && (
            <p className="mt-3 text-pretty text-muted-foreground">{description}</p>
          )}
        </div>
      )}
      {children}
    </section>
  );
}
