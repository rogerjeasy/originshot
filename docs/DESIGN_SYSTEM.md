# 01 · OriginShot Design System (PASTE THIS INTO v0 FIRST)

Paste the block below as your **first message** in the v0 project. It establishes OriginShot's entire visual language so every later screen is consistent, distinctive, and responsive. Everything after the block is notes for you (the builder), not for v0.

OriginShot's identity is deliberately **its own** — a gallery-grade product **studio in software**: crisp, editorial, confident, high-craft. Cool "seamless paper" neutrals, a single electric **cobalt** signal, an **emerald "Verified"** trust layer, **Geist Sans + Geist Mono** (mono carries every hash/SKU/price — a provenance-native detail). No warm creams, no serif headlines, no teal — a clean break from any softer, warmer system.

---

```
You are designing OriginShot — a gallery-grade product-photography studio in software. A seller uploads ONE ordinary phone photo of a product and OriginShot generates a full marketplace-ready pack: studio white-background shots, lifestyle scenes, on-model images, color/angle variants, and a short product video — every output carrying a verifiable provenance manifest (proof of what's authentic vs AI). Users are online sellers (Etsy/Shopify/Amazon/eBay), from solo makers to multi-SKU operators. It will be used daily by millions worldwide. Establish this design system and reuse it for every screen I ask for next.

PLATFORM (read first)
- OriginShot is a RESPONSIVE WEB APPLICATION that runs in the browser. It must look and work great on desktop browsers, laptops, tablets/iPad (portrait AND landscape), and mobile phone browsers — the SAME web app fluidly adapting to the viewport. It is NOT a native iOS/Android app. Where these prompts say "mobile" or "mobile-first", they mean the responsive web layout adapting to a small browser viewport (standard responsive CSS), not a separate app.

TECH
- Next.js App Router, TypeScript, Tailwind CSS (v4), shadcn/ui (install components as needed), lucide-react icons, recharts for charts, framer-motion (motion/react) for motion. Responsive web; mobile-first CSS.

BRAND PERSONALITY
- Studio-grade, precise, confident, premium, editorial. "Quiet craft." Think a high-end photography studio crossed with a modern developer tool: the product is the hero, lit perfectly on a seamless backdrop, and everything around it is calm scaffolding that gets out of the way.
- Image-FIRST: the generated media is the star of every screen. Big, beautifully framed thumbnails, locked aspect ratios, gallery grids, before/after, lightbox. UI chrome is restrained so photos pop.
- Trustworthy by design: provenance ("Verified") is a recurring, branded trust signal, not an afterthought.

ANTI-GENERIC (avoid the default AI look)
- NO purple/indigo gradients, NO neon glow, NO glassmorphism everywhere, NO emoji as UI icons, NO cramped dashboards, NO warm cream/beige backgrounds, NO serif display headlines, NO teal as a primary. Avoid pure #000 on pure #FFF. Color is a precise SIGNAL, not wallpaper — most of the interface is ink-on-paper neutral, with cobalt and emerald used sparingly and intentionally.

COLOR TOKENS — install as CSS variables (light / dark). Use semantic tokens, never raw hex in components.
Light ("Seamless"):
- background #F4F5F7 (cool seamless-paper neutral)   foreground #0E1116 (cool near-black ink)
- card #FFFFFF                                       card-foreground #0E1116
- popover #FFFFFF                                    popover-foreground #0E1116
- primary #14161B (studio ink)                       primary-foreground #FFFFFF   (default buttons/structure)
- secondary #EEF0F3                                  secondary-foreground #14161B
- accent #2F54EB (electric cobalt — the SIGNAL)      accent-foreground #FFFFFF    (key CTAs, links, focus; use sparingly)
- muted #EDEFF2                                      muted-foreground #5B6470
- border #E2E5EA   input #E2E5EA   ring #2F54EB
- verified #0E9F6E (emerald — provenance/authentic)  success #0E9F6E  warning #B45309  danger #DC2626  info #2F54EB
Dark ("Darkroom"):
- background #0B0D10   foreground #E7EAEE
- card #12151A         card-foreground #E7EAEE
- popover #12151A      popover-foreground #E7EAEE
- primary #F2F4F7 (light ink on dark)                primary-foreground #0B0D10
- secondary #1A1F26    secondary-foreground #E7EAEE
- accent #5B7BFF       accent-foreground #0B0D10
- muted #161A20        muted-foreground #9AA3AF
- border #232A33   input #232A33   ring #5B7BFF
- verified #2BD4A0  success #2BD4A0  warning #D98324  danger #F26464  info #5B7BFF
- Charts: cobalt, ink/graphite, emerald, slate, desaturated amber — never rainbow.

TYPOGRAPHY (distinctive on purpose)
- UI + display font: GEIST SANS (next/font via the `geist` package). Modern grotesk; broad glyph coverage. Headings semibold/medium with TIGHT tracking; large display can use a slightly negative letter-spacing. NO serif anywhere.
- Technical/metadata font: GEIST MONO. Use it for EVERYTHING machine-true: SHA-256 hashes, SKU codes, file sizes/dimensions, prices, run IDs, model names, timestamps. This mono treatment is a signature OriginShot detail tied to provenance — lean into it.
- Base 16px, line-height ~1.55 for body; in-app meaningful text never below 14px. Clear h1–h4 hierarchy. Tabular-nums for stats/tables.

SHAPE & DEPTH (crisp, gallery-framed — not pillowy)
- Use a consistent --radius = 0.625rem. Panels/cards rounded-xl; large media & hero rounded-2xl; controls/inputs rounded-lg; pills/badges rounded-full.
- IMAGE FRAMING is a core motif: media tiles get a 1px hairline border + a subtle inner ring (ring-1 ring-black/5) so photos read as "framed" gallery objects on the paper background. Lock aspect ratios (aspect-square for studio shots, aspect-[4/5] for lifestyle, aspect-video for video).
- Shadows: soft, low-opacity, cool-tinted (shadow-sm default; a slightly larger soft shadow on raised/hover). Prefer hairline border + subtle shadow over heavy elevation. No harsh black drop shadows.

SIGNATURE MOTIF — "the seamless sweep"
- Hero and empty states may use a subtle studio-sweep background: a very soft vertical gradient from background to a touch cooler/lighter near the top (like a photography seamless backdrop curving to the floor). Extremely restrained — barely-there, never a loud gradient. This is the one place gradient is allowed, and it must stay subtle.

PROVENANCE UI (brand-defining, reuse everywhere media appears)
- "Verified Original" / "AI-generated" status is shown as a small pill: icon (ShieldCheck / Sparkles) + text + color, plus a Geist-Mono truncated hash (e.g., `sha256 7f3a…b1c4`). Verified = emerald; AI-generated = ink/neutral with a Sparkles glyph. Status is ALWAYS icon + text + color (never color alone).
- A "Verify" action opens a panel showing integrity (pass/fail), model/provider (mono), and lineage to the authentic source. Make this feel trustworthy and precise, like a certificate.

SPACING & LAYOUT
- 4px spacing scale. Page padding px-4 sm:px-6 lg:px-8; vertical rhythm via gap utilities (not ad-hoc margins). Content max-width ~ max-w-7xl, centered. Cards use p-5/p-6. Gallery grids are the backbone: responsive auto-fit grids of framed media tiles.

⚖️ THE RESPONSIVENESS LAW (must hold on EVERY screen, no exceptions)
- This is a WEB app: every screen must be flawless across ALL browser viewports — mobile phone browser (320–767px), tablet/iPad portrait & landscape (768–1023px), laptop (1024–1279px), desktop (1280px+), up to 4K. Verify each of these four classes.
- Flawless from 320px to 4K. ZERO horizontal page scroll. ZERO content overflow. ZERO overlapping elements at any width.
- Layout with responsive flex/grid; add min-w-0 to flex/grid children so text can truncate instead of pushing layout. Media: max-w-full h-auto, locked aspect-ratio, object-cover inside framed tiles. Long text: truncate or break-words. Hashes/SKUs/prices in mono must truncate (with copy affordance), never force overflow.
- Gallery grids fold step by step (e.g., 5→4→3→2→1 or 4→2→1) — never all at once. Tables become stacked cards on small screens OR live inside an overflow-x-auto container that is itself contained — the PAGE never scrolls sideways.
- Sticky headers/upload bars must be safe-area aware (env(safe-area-inset-*)). Modals/sheets and the lightbox fit small viewports (max-h with internal scroll).
- Breakpoints (Tailwind): mobile-first, refine at sm(640) md(768 = tablet/iPad) lg(1024 = laptop) xl(1280 = desktop) 2xl(1536). Tablet/iPad gets a REAL intermediate layout (2-column workspace or a collapsed icon rail) — never a stretched-out phone view. Sidebars collapse to an icon rail; the studio workspace reflows gracefully.

MOTION SYSTEM (precise, quick, gallery-like)
- 120–220ms, ease-out. Media reveals: fade-in + slight scale from 0.98 → 1, with small stagger across a grid (a "developing"/print-coming-to-life feel). Cards: subtle hover lift (translate-y-0.5 + soft shadow + ring). Stat counters animate up (tabular-nums). Lightbox opens with a soft spring; accordions/sheets ease smoothly. Page content does a gentle fade-in.
- Loading skeletons use a cool shimmer that reads like a photo "developing" — image-shaped placeholders, not generic gray bars, wherever media will appear.
- ALWAYS honor prefers-reduced-motion: replace movement with instant/opacity-only. Never animate in a way that blocks interaction.

ACCESSIBILITY (WCAG AA)
- Visible focus rings (ring token, 2px) on all interactive elements. Keyboard operable; lightbox/dialogs are focus-trapped and escape-closable. Semantic HTML + aria labels. 44px min touch targets. Contrast AA for text and UI. Status uses icon + text + color (never color alone). Forms have labels, helper text, and clear inline errors. Provide descriptive alt text for generated media.

INTERNATIONALIZATION
- Use CSS logical properties (ms/me/ps/pe, start/end) so RTL works. Leave room for ~30% text expansion. Locale-aware dates/numbers/currency. No text baked into images.

REQUIRED STATES on every data view: loading (image-shaped "developing" skeletons), empty (clean framed illustration + guidance + primary action, e.g., "Drop a product photo to start your first studio pack"), error (calm retry with a correlation hint). Confident, plain microcopy ("12 shots ready · all verified", "Studio pack generated", "Verified original") — never robotic ("0 errors").

COMPONENT CONVENTIONS (shadcn): Button (default=ink primary, secondary, ghost, destructive, plus an accent/cobalt variant for the single key CTA per screen; sizes sm/default/lg), Card, Badge, Avatar, Tabs, Dialog (desktop) / Sheet (mobile drawers), Sidebar (collapses to icon rail), Tooltip, DropdownMenu, Table, Calendar, Form (react-hook-form + zod), Sonner toasts, Skeleton, Progress, Separator, ScrollArea, Tabs. Charts via shadcn/recharts. Keep ONE consistent set.
- OriginShot-specific patterns to define and reuse: UploadDropzone (the hero input), GalleryGrid + ImageTile (framed, with provenance pill + hover actions), BeforeAfter slider (original → studio), StylePicker (studio/lifestyle/on-model/variants/video), MarketplacePresetSelector (Amazon/Etsy/Shopify/eBay/Social), JobProgress (per-style tiles with developing skeletons), ProvenanceBadge + VerifyPanel, StatCard (mono numbers), Lightbox.

Acknowledge by generating a compact "Design tokens & components" style-guide screen: color swatches (with token names), the Geist Sans + Geist Mono type scale, all button variants/sizes, badges incl. the Verified/AI provenance pills, a sample framed ImageTile with a provenance pill, a small StatCard, and a light/dark toggle — so I can verify the system. Make it responsive per the Responsiveness Law.
Remember: responsive web app. Show it working at 375px (phone browser), 820px (iPad portrait), 1024px (iPad landscape/laptop), and 1440px (desktop) — no horizontal scroll, no overflow, and the iPad layout is a REAL tablet layout, not a stretched phone view.
```

---

## Notes for the builder (not for v0)

**Why this looks nothing like a "default AI app" (and nothing like warmer systems):**
- **Cool ink-on-paper, not warm cream.** The base is a cool seamless-paper neutral with cool near-black ink — a studio, not a kitchen.
- **One signal color.** Cobalt is a precise accent (CTAs, links, focus), emerald is reserved for trust/provenance. The interface is mostly neutral so the *photos* are the color.
- **Geist Sans + Geist Mono**, no serif. The mono-everywhere-technical treatment (hashes, SKUs, prices, model names) is the ownable signature and ties directly to the provenance product story.
- **Gallery framing + the seamless-sweep motif** make the app feel like a photography studio rather than a generic dashboard.

**Fonts:** install the `geist` package and load `GeistSans` / `GeistMono` via `next/font` in `app/layout.tsx`; wire them to `--font-sans` / `--font-mono` and reference those in the Tailwind theme. (The starter frontend in `../frontend` already encodes these tokens in `app/globals.css` and demonstrates them on the home/style-guide page — keep v0 output consistent with it.)

**Token mapping for Tailwind v4:** define the tokens above as CSS variables under `:root` and `.dark` in `globals.css`, then expose them through `@theme inline` (e.g., `--color-background`, `--color-primary`, `--color-accent`, `--color-verified`, `--radius`). Drive dark mode with a `.dark` class on `<html>`.

**Suggested screen order to ask v0 for next:** (1) this style guide → (2) marketing/landing with the seamless-sweep hero → (3) auth (sign in/up) → (4) the Studio workspace (upload → style/preset pick → generate) → (5) Job progress with developing skeletons → (6) SKU gallery with provenance pills + lightbox → (7) public Verify page → (8) Analytics dashboard (recharts, mono stats) → (9) Settings/Brand kit. Each must obey the Responsiveness Law and reuse the components above.

**Consistency rule:** every screen reuses the tokens, the framed ImageTile, and the ProvenanceBadge. If a new color is ever needed, add it as a semantic token here first — never hardcode hex in a component.
