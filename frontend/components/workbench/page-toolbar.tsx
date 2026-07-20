import type { ReactNode } from "react";
import Link from "next/link";
import { ChevronRight } from "lucide-react";

import { cn } from "@/lib/utils";

export type Crumb = { label: string; href?: string };

/**
 * The head of every screen: where you are, what this is, what you can do here.
 *
 * The old PageHeader set titles at text-2xl in the interface face, which is the
 * same treatment as a section heading three levels down — nothing told you the
 * page had changed. Here the title is the one place the display face appears in
 * the app, at the size the system reserves it for (never below ~1.75rem), so a
 * screen announces itself once and then gets out of the way.
 *
 * The trail is set in mono because it's a path, and paths in this product are
 * addresses you can check — the same face the hashes use.
 */
export function PageToolbar({
  title,
  description,
  crumbs,
  action,
  meta,
  className,
}: {
  title: string;
  description?: string;
  /** Ancestors only — the current page is the title, never repeated as a crumb. */
  crumbs?: Crumb[];
  action?: ReactNode;
  /** Status or counts that belong to the screen rather than to any one region. */
  meta?: ReactNode;
  className?: string;
}) {
  return (
    <header className={cn("min-w-0", className)}>
      {crumbs && crumbs.length > 0 && (
        <nav aria-label="Breadcrumb" className="mb-3">
          <ol className="flex flex-wrap items-center gap-1">
            {crumbs.map((c) => (
              <li key={c.label} className="flex items-center gap-1">
                {c.href ? (
                  <Link
                    href={c.href}
                    className="label-mono rounded-sm text-muted-foreground transition-colors hover:text-foreground"
                  >
                    {c.label}
                  </Link>
                ) : (
                  <span className="label-mono text-muted-foreground">{c.label}</span>
                )}
                <ChevronRight aria-hidden className="size-3 text-muted-foreground/50" />
              </li>
            ))}
          </ol>
        </nav>
      )}

      <div className="flex flex-wrap items-end justify-between gap-x-6 gap-y-4">
        <div className="min-w-0">
          <h1 className="display font-display text-[1.75rem] sm:text-[2rem]">{title}</h1>
          {description && (
            <p className="mt-2 max-w-2xl text-[0.9375rem] text-muted-foreground">
              {description}
            </p>
          )}
        </div>
        {action && <div className="flex shrink-0 flex-wrap items-center gap-2">{action}</div>}
      </div>

      {meta && <div className="mt-4 flex flex-wrap items-center gap-x-5 gap-y-2">{meta}</div>}
    </header>
  );
}
