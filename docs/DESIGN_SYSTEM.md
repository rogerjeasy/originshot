# OriginShot Design System — "Calibration"

The source of truth for OriginShot's visual language. Tokens live in
`frontend/app/globals.css`; this document explains what they mean and why.

---

## The thesis

Every semantic colour in this system is a patch from the **ColorChecker chart** —
the 24-square reference card photographers shoot to prove their colour is
truthful.

For a product whose entire claim is *verifiable photographic authenticity*, the
instrument of photographic truth is the right source material. It gives the
system three things a chosen-from-nowhere palette can't:

1. **Colours with provenance of their own.** These are standardised, measured,
   slightly desaturated values. They read as expensive precisely because they
   aren't SaaS colours.
2. **A neutral ramp that comes from somewhere.** The greys are the chart's own
   greyscale patches (19–24), so the interface stays achromatic and the
   generated photographs are the only real colour on screen.
3. **A defensible chart palette.** Analytics uses patch hues in a fixed order,
   so categorical series never need an arbitrary decision.

**What this system deliberately is not:** no cream-and-terracotta editorial, no
near-black-with-one-acid-accent, no broadsheet hairline pastiche, and no
Geist/cobalt developer-tool look. Those are defaults, not choices.

---

## Colour

Tokens are semantic. **Never write a raw hex in a component** — if a new colour
is needed, add it here first.

### Light — "Daylight" (the card shot at 5000K)

| Token | Value | Patch |
| --- | --- | --- |
| `background` | `#EDEDE9` | below patch 19 white, so white cards frame |
| `foreground` | `#1A1A18` | below patch 24 black, for AA body contrast |
| `card` / `popover` | `#FFFFFF` | — |
| `primary` | `#1F1F1D` | studio ink |
| `secondary` | `#E4E4E0` | — |
| `muted` | `#E8E8E4` | — |
| `muted-foreground` | `#6B6B64` | patch 22, darkened to AA |
| `border` / `input` | `#DCDCD7` | — |
| `accent` / `ring` | `#383D96` | **patch 13 · blue — the signal** |
| `verified` / `success` | `#3B7C3D` | patch 14 green, darkened to AA |
| `warning` | `#9E5A15` | patch 7 orange, darkened to AA |
| `danger` | `#A83239` | patch 15 red |
| `info` | `#06697F` | patch 18 cyan, darkened to AA |

Each status colour also has a `-surface` companion (`verified-surface`,
`warning-surface`, `danger-surface`, `info-surface`) for tinted badge and alert
grounds.

### Dark — "Darkroom" (the card under safelight)

Same roles, patches lifted for legibility against `#121211`. See `.dark` in
`globals.css`.

### Chart ramp

**The raw patches fail as a data palette.** Validated with the six checks, patch
13 sits below the lightness band, patches 5 and 22 read as grey, and patches
18/5 are indistinguishable under protanopia (ΔE 2.6). Aesthetic provenance
doesn't buy accessibility.

`--chart-1` … `--chart-4` are those patch hues **re-stepped until every check
passes**, in this fixed order — orange, blue, green, magenta:

```
node scripts/validate_palette.js "#C67B1E,#3F49BE,#1E8A4E,#B563A6" --mode light
node scripts/validate_palette.js "#C4822C,#6F78DD,#35A65E,#C574B6" --mode dark
```

Four slots, not eight: a fifth passing hue doesn't exist at this chroma without
colliding with one already in the set. A fifth series folds into "Other" or gets
faceted — it is never a generated hue.

Dark steps are **selected against the darkroom surface**, not flipped from light.

**Assign in fixed order, never cycled.** Colour follows the entity, never its
rank, so a filter that changes the series count must not repaint the survivors.

### When not to use the ramp

Most charts here are one series. Provider mix is counts by category — a
magnitude comparison, so it takes **one hue** (the accent) and direct value
labels. Colour that only restates the axis label is noise. Reach for the
categorical ramp only when colour is genuinely carrying identity.

### Rules

- **The accent is a signal, not decoration.** One `accent` action per screen. If
  two things on a screen are cobalt, neither reads as the primary action.
- **Colour is used flat.** No gradients on interactive surfaces. The only
  gradients in the system are the calibration-grid backdrop and the `developing`
  shimmer.
- **Status is always icon + text + colour**, never colour alone.

---

## Type

Two families, three roles.

- **Archivo** (`--font-sans`) — a grotesk drawn for print and screen
  performance. Carries the whole interface.
- **IBM Plex Mono** (`--font-mono`) — carries everything machine-true: SHA-256
  hashes, SKU codes, model names, dimensions, timestamps, prices, run IDs.

The typographic signature is **width tension**:

| Class | Use |
| --- | --- |
| `.display` | Hero headlines. `-0.035em` tracking, line-height 1.02. |
| `h1`–`h4` | `-0.022em` tracking, weight 600, balanced wrapping. |
| `.label` | Micro-labels: 11px, uppercase, `0.14em` tracking, weight 600. |
| `.label-mono` | Same, in mono — for technical legends and rebate strips. |
| `.tabular` | `tabular-nums` for any figure that sits in a column. |

Headlines are set tight and heavy; micro-labels are set small, wide, and
uppercase — like the legend printed along the bottom edge of a calibration card.
That contrast, not a decorative typeface, is what makes the system recognisable.

**The mono/sans split carries meaning:** sans is what we claim, mono is what can
be checked. Keep it honest — don't set marketing copy in mono for texture.

---

## Shape, depth, framing

- `--radius: 0.5rem`. Panels `rounded-lg`, media `rounded-md`, pills
  `rounded-full`.
- Depth comes from a **hairline border first**, elevation second. Three shadow
  tokens only: `shadow-hairline`, `shadow-raised`, `shadow-float`.
- **`.frame`** — the media motif. A 1px inset ring so every generated asset
  reads as a mounted print against the neutral ground. **`.frame-deep`** adds
  float elevation for hero media.
- Aspect ratios are locked per style so grids never reflow as assets land:
  `aspect-square` (studio, variant), `aspect-[4/5]` (lifestyle, on-model),
  `aspect-video` (video).

---

## Signature motifs

- **`.patch-grid`** — the calibration lattice, at 72px. Pair with
  `.patch-grid-fade` to mask it toward the edges. Used on the hero and the
  closing CTA. This is the system's one piece of ambient decoration; don't add a
  second.
- **The contact sheet** (`components/marketing/contact-sheet.tsx`) — the hero's
  centrepiece. Uniform frames, a mono rebate strip, and each frame's **real**
  SHA-256 beneath it, linking to `/verify`. The proof on the marketing site is
  checkable rather than claimed.
- **`.developing`** — loading shimmer for anywhere media will land. A print
  coming up in the tray, not a grey bar. Use `MediaSkeleton`, not `Skeleton`,
  wherever an image is coming.

---

## Motion

120–220ms, ease-out. Media reveals fade in with a slight scale from 0.98,
staggered across a grid. Cards lift 2px on hover (`.lift`). Overlays animate off
Radix `data-state` via `.anim-overlay` / `.anim-pop` / `.anim-pop-plain` — there
is **no animation library beyond framer-motion**; don't add `tailwindcss-animate`.

`prefers-reduced-motion` is honoured globally in `globals.css`. Never rely on a
component to remember.

---

## Components

Primitives live in `frontend/components/ui/` and are Radix-backed where
behaviour matters (dialog, tabs, tooltip, progress, label, separator).

Composite patterns to reuse rather than re-invent:

| Component | Role |
| --- | --- |
| `ProvenanceBadge` | The trust signal. Icon + text + colour + mono hash. |
| `ImageTile` | A generated asset as a mounted print, with caption strip. |
| `AssetWorkbench` | The pack grouped by style, with slots held for pending frames. |
| `ContactSheet` | The marketing hero's proof surface. |
| `BrandMark` | Four-patch calibration glyph, one patch struck in verified green. |
| `StatCard` / `StatGrid` | Metrics in a hairline-divided grid — no card-in-a-card. Figures are mono and tabular. |
| `ProviderChart` | A real `<table>`, not a charting library. There is **no chart dependency** in this project; don't reintroduce one for a handful of bars. |
| `Field` | Label + control + hint/error. Wires `aria-describedby` and `aria-invalid` — use it instead of hand-assembling a `Label` and an `Input`. |
| `AccountPanel` | Identity and sign-out on Settings. Sign-out is deliberately duplicated from the sidebar rail. |
| `Card` | `CardTitle` is a **micro-label** (names a region); `CardHeading` is a real heading (names content). Picking the wrong one is the easiest mistake to make here. |

---

## Responsiveness

Must hold on every screen, no exceptions:

- Flawless 320px → 4K. **Zero horizontal page scroll, zero overflow, zero
  overlap** at any width.
- `min-w-0` on flex/grid children so text truncates instead of pushing layout.
- Tables scroll inside their own container (`Table` does this already) — the
  page never scrolls sideways.
- Hashes and SKUs truncate; they never force overflow.
- Grids fold stepwise (4→2→1), never all at once.
- Tablet gets a real intermediate layout — the sidebar collapses to an icon
  rail, not a stretched phone view.
- Sticky bars are safe-area aware (`env(safe-area-inset-*)`).

Verify with `scripts/` + Playwright at 390 / 820 / 1440, light and dark. The
screenshot harness asserts no horizontal overflow.

---

## Accessibility

WCAG AA. One focus treatment, defined once on `:focus-visible` in `globals.css`
— don't re-style focus per component. 44px minimum touch targets. Status is
never colour alone. Every form control has a label; `Field` wires up
`aria-describedby` and `aria-invalid` for you. Generated media needs descriptive
alt text.

---

## Content

Words are design material. Name things by what the user controls. Active voice;
a control says what happens when it's used, and keeps the same name through the
flow. Errors state what happened and what to do — they don't apologise and
they're never vague. Empty states are an invitation to act.

**Never state a number the code doesn't support.** Figures on the marketing site
(assets per pack, timings) come from `backend/app/pricing.py`; if `_OUTPUTS` or
`_ETA_SECONDS` change, the copy changes with them.
