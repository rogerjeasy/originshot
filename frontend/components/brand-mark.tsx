import Link from "next/link";

import { cn } from "@/lib/utils";

/**
 * The OriginShot lockup.
 *
 * The glyph is a four-patch calibration square — the reference card a
 * photographer shoots to prove their colour is truthful — with one patch struck
 * in the verified green. It says what the product does in one mark: of the
 * things in this frame, exactly one is the checked original.
 *
 * Single source of truth so the brand reads identically in the app shell,
 * public headers, and marketing pages.
 */
export function BrandMark({
  href,
  className,
  wordmarkClassName,
  size = "default",
}: {
  /** When set, the mark is a link (e.g. "/" on public pages). */
  href?: string;
  className?: string;
  /** Override wordmark visibility, e.g. "hidden lg:inline" in a collapsed rail. */
  wordmarkClassName?: string;
  size?: "default" | "lg";
}) {
  const box = size === "lg" ? "size-9" : "size-8";
  const word = size === "lg" ? "text-xl" : "text-[17px]";

  const content = (
    <>
      <span
        className={cn("grid shrink-0 place-items-center rounded-md bg-primary p-1.5", box)}
        aria-hidden
      >
        <svg viewBox="0 0 20 20" className="size-full" role="presentation">
          <rect x="0" y="0" width="9" height="9" rx="1.5" className="fill-verified" />
          <rect
            x="11"
            y="0"
            width="9"
            height="9"
            rx="1.5"
            className="fill-primary-foreground"
            opacity="0.45"
          />
          <rect
            x="0"
            y="11"
            width="9"
            height="9"
            rx="1.5"
            className="fill-primary-foreground"
            opacity="0.25"
          />
          <rect
            x="11"
            y="11"
            width="9"
            height="9"
            rx="1.5"
            className="fill-primary-foreground"
            opacity="0.7"
          />
        </svg>
      </span>
      <span
        className={cn("truncate font-semibold tracking-[-0.03em]", word, wordmarkClassName)}
      >
        OriginShot
      </span>
    </>
  );

  const classes = cn("flex min-w-0 items-center gap-2.5", className);

  return href ? (
    <Link href={href} className={classes} aria-label="OriginShot home">
      {content}
    </Link>
  ) : (
    <div className={classes}>{content}</div>
  );
}
