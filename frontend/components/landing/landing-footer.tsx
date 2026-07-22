import Link from "next/link";

import { BrandMark } from "@/components/brand-mark";

const GROUPS = [
  {
    heading: "Product",
    links: [
      { href: "/studio", label: "Studio" },
      { href: "/library", label: "Library" },
      { href: "/analytics", label: "Analytics" },
    ],
  },
  {
    heading: "Proof",
    links: [
      { href: "/check", label: "Check a listing" },
      { href: "/verify", label: "Verify a file" },
      { href: "/ledger", label: "Transparency log" },
      { href: "/resolve", label: "Resolve a dispute" },
    ],
  },
  {
    heading: "Learn",
    links: [
      { href: "/pack", label: "See a real pack" },
      { href: "/how-it-works", label: "How it works" },
      { href: "/about", label: "About" },
      { href: "/style-guide", label: "Design system" },
    ],
  },
];

/** Footer for the landing page, which closes on ink and so cannot use the
 *  shared SiteFooter's app-token surface. */
export function LandingFooter() {
  return (
    <footer className="band-ink border-t">
      <div className="mx-auto grid max-w-[1320px] gap-12 px-5 py-16 sm:px-8 lg:grid-cols-[1.6fr_1fr_1fr_1fr]">
        <div className="max-w-xs">
          <BrandMark href="/" />
          <p className="on-ink-mute mt-4 text-[14px] leading-relaxed">
            One phone photo in, a marketplace-ready catalog out — with a checkable record of
            what&apos;s real and what&apos;s AI.
          </p>
        </div>

        {GROUPS.map((g) => (
          <nav key={g.heading} className="flex flex-col gap-3.5">
            <p className="kicker on-ink-mute">{g.heading}</p>
            {g.links.map((l) => (
              <Link
                key={l.href}
                href={l.href}
                className="on-ink-mute text-[14px] transition-colors hover:text-[var(--ink-fg)]"
              >
                {l.label}
              </Link>
            ))}
          </nav>
        ))}
      </div>

      <div className="border-t">
        <div className="mx-auto flex max-w-[1320px] flex-col gap-2 px-5 py-6 sm:flex-row sm:items-center sm:justify-between sm:px-8">
          <p className="on-ink-mute font-mono text-[11.5px]">
            Generated with Genblaze · Stored on Backblaze B2
          </p>
          <p className="on-ink-mute font-mono text-[11.5px]">© 2026 OriginShot</p>
        </div>
      </div>
    </footer>
  );
}
