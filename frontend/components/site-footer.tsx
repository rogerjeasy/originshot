import Link from "next/link";

import { BrandMark } from "./brand-mark";

const GROUPS: { heading: string; links: { href: string; label: string }[] }[] = [
  {
    heading: "Product",
    links: [
      { href: "/studio", label: "Studio" },
      { href: "/verify", label: "Verify" },
      { href: "/analytics", label: "Analytics" },
    ],
  },
  {
    heading: "Learn",
    links: [
      { href: "/how-it-works", label: "How it works" },
      { href: "/about", label: "About" },
      { href: "/style-guide", label: "Design system" },
    ],
  },
];

/** Shared site footer for public pages. */
export function SiteFooter() {
  return (
    <footer className="border-t">
      <div className="mx-auto grid max-w-7xl gap-10 px-4 py-12 sm:px-6 lg:grid-cols-[1.5fr_1fr_1fr] lg:px-8">
        <div className="max-w-xs">
          <BrandMark href="/" />
          <p className="mt-3 text-sm text-muted-foreground">
            One phone photo in, a full marketplace-ready catalog out — with cryptographic proof of
            what&apos;s real and what&apos;s AI.
          </p>
        </div>
        {GROUPS.map((g) => (
          <nav key={g.heading} className="flex flex-col gap-3">
            <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              {g.heading}
            </p>
            {g.links.map((l) => (
              <Link
                key={l.href}
                href={l.href}
                className="text-sm text-muted-foreground transition-colors hover:text-foreground"
              >
                {l.label}
              </Link>
            ))}
          </nav>
        ))}
      </div>
      <div className="border-t">
        <div className="mx-auto flex max-w-7xl flex-col gap-2 px-4 py-6 sm:flex-row sm:items-center sm:justify-between sm:px-6 lg:px-8">
          <p className="text-sm text-muted-foreground">
            Generated with Genblaze · Stored on Backblaze B2
          </p>
          <p className="font-mono text-xs text-muted-foreground">responsive 320px → 4K</p>
        </div>
      </div>
    </footer>
  );
}
