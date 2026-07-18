import { cn } from "@/lib/utils";

/**
 * Shared marketing section frame.
 *
 * Headings sit left rather than centred: the page reads as a document making an
 * argument, and a left edge gives the eye something to run down.
 */
export function Section({
  eyebrow,
  title,
  description,
  align = "start",
  className,
  children,
}: {
  eyebrow?: string;
  title?: string;
  description?: string;
  align?: "start" | "center";
  className?: string;
  children: React.ReactNode;
}) {
  const centered = align === "center";
  return (
    <section
      className={cn("mx-auto max-w-[1400px] px-4 py-16 sm:px-6 sm:py-24 lg:px-8", className)}
    >
      {(eyebrow || title || description) && (
        <div className={cn("max-w-2xl", centered && "mx-auto text-center")}>
          {eyebrow && <p className="label text-muted-foreground">{eyebrow}</p>}
          {title && (
            <h2 className="mt-3 text-balance text-3xl font-semibold tracking-[-0.03em] sm:text-4xl">
              {title}
            </h2>
          )}
          {description && (
            <p className="mt-4 text-pretty text-muted-foreground sm:text-lg">{description}</p>
          )}
        </div>
      )}
      {children}
    </section>
  );
}

/** Back-compat alias — older pages import MarketingSection. */
export { Section as MarketingSection };
