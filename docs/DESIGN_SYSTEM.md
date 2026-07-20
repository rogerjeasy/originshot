# OriginShot Design System — "Light Table"

The source of truth for OriginShot's visual language, across the marketing site
and the signed-in app. Tokens live in `frontend/app/globals.css`; this document
explains what they mean and why.

> **Supersedes "Calibration"** (the ColorChecker-patch system, 2026-07-18).
> Calibration's neutrals and type have been retired; several of its rules were
> right and are carried forward verbatim, marked where they appear. The
> migration ledger at the end records exactly what has moved and what hasn't.

---

## The thesis

The product's claim is that a photograph can be checked. So the interface is the
room you check photographs in: **a photographer's light table.**

Two surfaces, alternating:

- **Ink** — a deep, daylight-balanced viewing ground. Photographs and lit
  objects sit on it. Nothing competes with them.
- **Paper** — a near-white reading ground. Records, tables, prose, and anything
  a person has to study rather than look at.

And one chromatic axis, taken from photography's own vocabulary: **colour
temperature.**

| Temperature | Colour | Means |
| --- | --- | --- |
| 3200K tungsten | `#E9A13B` | **Do something.** Every primary action, and only those. |
| 5600K daylight | `#46B6CF` | **This checked out.** Verification, provenance, machine-true values. |

There is no third accent. A page that needs a third accent needs an edit
instead. Because the palette is only two hues plus neutrals, the generated
product photographs are the only other colour on any screen — which is the whole
point of the product.

**What this system deliberately is not:** no cream-and-terracotta editorial, no
near-black-with-one-acid-accent, no broadsheet hairline pastiche, no
Geist/cobalt developer-tool look. Those are defaults, not choices.

---

## Bands

**The band is the unit of page layout.** A band is a full-bleed horizontal
region that declares which room it is, using `.band-ink` or `.band-paper`. Pages
are built by alternating them; sections do not float on an undifferentiated
background.

A band sets four things for everything inside it: surface colour, text colour,
hairline colour, and — critically — the two **accent text tokens**. Author with
`.t-accent` and `.t-verify` and the correct value resolves per band, without the
component needing to know where it sits.

```
┌──────────────────────────────── ink ───┐   hero, mechanism, closing
│  photographs, lit objects, the pitch   │
├────────────────────────────── paper ───┤   records, tables, prose, FAQ
│  things a person reads carefully       │
└────────────────────────────────────────┘
```

In dark mode the paper band does **not** flip to white — it becomes a second,
lighter room, so the two-band rhythm survives the theme.

### Where bands apply — and where they don't

Bands are a **narrative** device: they pace a page that argues. That makes them
right for the marketing surface and wrong for a tool.

| Surface | Treatment |
| --- | --- |
| `/`, `/how-it-works`, `/about`, `/signin` | **Full band rhythm.** Alternating ink and paper, `viewing-light`, `kelvin-rule`. |
| `/verify`, `/ledger` (signed out) | **`.ink-ground` + `.surface`.** The viewing room as a ground, carrying ordinary app panels. |
| `/resolve` and the whole signed-in app | **Tokens, type and motifs — no bands.** Same neutrals, same `.t-accent`/`.t-verify`, same `.plate`/`.frame`, on the app's own surface. |

#### `.ink-ground` / `.surface`

A third case the two above don't cover: a page that should sit in the viewing
room but is built from ordinary app components (`Card`, `Alert`, `Input`, the
dropzone) rather than band-native ones.

`.band-ink` is wrong for this. Its `.band-ink *` rule repaints **every**
descendant hairline to `--ink-line`, so a white card inside it ends up mixing
navy rules with the grey ones drawn by `bg-border` — one panel, two hairline
colours. `.ink-ground` sets the surface, the text colour and the accent-text
bindings, and nothing else.

`.surface` is its counterpart, for any panel keeping its own paper surface on
that ground. It shifts `--muted-foreground`, `--accent-text` and `--verify-text`
back, so components inside render correctly without knowing where they are.

> **The rule: every panel with its own surface on `.ink-ground` needs
> `.surface`.** Miss it and `text-muted-foreground` inside that panel stays
> bound to `--ink-mute` and renders light-on-light. This is what lets
> `/verify` and `/ledger` be the *same file* signed-out on ink and signed-in
> inside the app shell, with neither version hardcoding a colour — on the app
> ground `.ink-ground` is simply absent.

`AdaptiveChrome` takes `ground="ink"`, which applies **only when signed out**.
Inside the app shell the content area sits beside a themed sidebar, where a
permanently dark panel reads as a rendering fault rather than a choice.

#### The app stays on paper — deliberately

Signing in moves you from a permanently-ink public surface to an app that
follows the system preference (`--background`: `#F6F5F2` light, `#0E1823` dark).
On a light-preference machine that is a visible flip at the moment of sign-in.

**This is intended, and it follows the thesis at the top of this document:** ink
is the ground you *look at* photographs on, paper is the ground you *study*
records on. The app is where records are studied. You leave the gallery and
enter the workroom.

Do not "fix" the flip by darkening the app without deciding to move the whole
signed-in product into the viewing room — half-darkening it (ink chrome, paper
content) trades one discontinuity for a smaller one in more places.

**Theme selection is system-only.** The toggle is gone, so nothing can write a
stored preference; the pre-paint script clears any legacy `theme` key it finds.
Preferring a stored value over the system was correct while a control existed to
change it, but once the control was removed it pinned anyone who had ever chosen
light to light permanently, with no way to reach the setting.

The reason is structural, not stylistic: `/verify`, `/ledger` and `/resolve`
render inside `AdaptiveChrome`, so the same file is a public page for a
signed-out buyer *and* an app screen inside the sidebar shell. A full-bleed
alternating band inside a sidebar layout reads as a broken container. `/signin`
takes the full treatment because it has no shell — it is the threshold into the
studio, so it is the one dark room you pass through on the way in.

> **Consequence for `.t-accent`.** Because most of the app is *not* inside a
> band, `--accent-text` and `--verify-text` are bound at `:root` and `.dark` as
> well as per band. Without the root binding, `.t-accent` fell through to its
> `--tungsten-ink` fallback and measured **2.99:1** on the dark app ground.

---

## Colour

Tokens are semantic. **Never write a raw hex in a component.**

### The temperature pair

| Token | Value | Use |
| --- | --- | --- |
| `--tungsten` | `#E9A13B` | Fills and strokes on ink. Buttons, progress, nodes. |
| `--tungsten-ink` | `#8A5512` | The same hue, legible as text on paper. |
| `--daylight` | `#46B6CF` | Fills and strokes on ink. |
| `--daylight-ink` | `#0F6D85` | The same hue, legible as text on paper. |

### ⚠ The contrast law

`--tungsten` and `--daylight` are **light colours**. As text on paper they
measure **2.00:1** and **2.18:1** — both far below the 4.5:1 AA floor. This is
not a theoretical risk; it shipped once and had to be fixed across six
components.

> **Never set text to `--tungsten` or `--daylight` directly. Use `.t-accent` and
> `.t-verify`,** which each band binds to the legible member of that family
> (5.68:1 and 5.43:1 on paper; 8.48:1 and 7.80:1 on ink).

Using the full-chroma tokens as a **fill** — a button, a dot, a progress bar, a
1px rule — is correct and intended. The law is about type.

> **`--accent` is now tungsten, and `--accent` is a fill.** The app's primary
> action was moved onto the temperature axis, so `bg-accent` is `#E9A13B` with
> `--accent-foreground` `#16110a` on top (8.60:1 — white would have been 2.18:1).
> There is deliberately **no `text-accent`**: the 27 sites that used it were
> migrated to `.t-accent`, because the moment `--accent` became tungsten every
> one of them would have measured 2.00:1. This is the second time this exact
> failure was caught; the checker below exists so there is no third.
>
> `--ring` is `--tungsten-ink`, not `--tungsten` — a focus ring has to hold its
> own against paper.

Check any new pair before shipping it:

```
node -e 'function L(h){const c=[1,3,5].map(i=>parseInt(h.substr(i,2),16)/255).map(v=>v<=0.03928?v/12.92:Math.pow((v+0.055)/1.055,2.4));return 0.2126*c[0]+0.7152*c[1]+0.0722*c[2]}
function CR(a,b){const x=L(a),y=L(b);return ((Math.max(x,y)+0.05)/(Math.min(x,y)+0.05)).toFixed(2)}
console.log(CR("#8a5512","#f6f5f2"))'
```

### Neutrals

| Role | Ink band | Paper band |
| --- | --- | --- |
| surface | `--ink` `#0B1420` | `--paper` `#F6F5F2` |
| raised | `--ink-2` `#101C2B` | `--paper-2` `#FFFFFF` |
| inset | `--ink-3` `#16273A` | — |
| hairline | `--ink-line` `#23364A` | `--paper-line` `#E3E1DB` |
| text | `--ink-fg` `#EEF3F8` | `--paper-fg` `#121A22` |
| muted text | `--ink-mute` `#94A8BD` (7.32:1) | `--paper-mute` `#5C6A79` (5.08:1) |

The app's semantic tokens (`--background`, `--card`, `--border`,
`--muted-foreground`, …) are mapped onto these families in both themes, so an
app screen and a marketing page are the same room. Component code keeps using
the semantic names.

### Status colours

`--danger`, `--info` and `--verified` and their `-surface` companions are
unchanged from Calibration and remain in use across the app.

> **The collision, and how it was resolved.** Calibration's `--warning`
> (`#9E5A15`) was a burnt amber sitting **ΔE 8.2** from `--tungsten-ink` — close
> enough to be the same colour. It was harmless only while `--accent` was still
> cobalt. When `--accent` moved to tungsten, `--warning` moved in the same
> change, as required:
>
> | | Light | Dark |
> | --- | --- | --- |
> | `--warning` | `#A6431C` | `#E2703F` |
> | `--warning-surface` | `#FBEFE9` | `#2A1A14` |
>
> The new sienna is ΔE 22.1 from tungsten and ΔE 21.0 from `--danger` in light,
> ΔE 29.4 / 29.9 in dark — separable from both neighbours rather than trading one
> collision for another. Warning and danger are additionally always
> icon + text + colour, never colour alone.

**Separation is now enforced, not remembered.** `frontend/scripts/validate-contrast.js`
parses `globals.css` and fails on any AA breach *or* any pair of
different-meaning hues drifting under ΔE 15:

```
node scripts/validate-contrast.js   # exits non-zero on failure
```

Run it after touching any colour token. It reads the real values rather than
restating them, so it cannot drift from what ships.

### Chart ramp *(carried forward from Calibration, unchanged)*

The raw ColorChecker patches fail as a data palette. `--chart-1` … `--chart-4`
are those hues re-stepped until every check passes, in fixed order — orange,
blue, green, magenta:

```
light  #C67B1E  #3F49BE  #1E8A4E  #B563A6
dark   #C4822C  #6F78DD  #35A65E  #C574B6
```

> ⚠ **Unverified.** Earlier revisions of this document invoked
> `scripts/validate_palette.js` here. **That script was never committed** — the
> command does not run, and the ramp above is the recorded output of a check
> that can no longer be reproduced. The ramp is untouched by the tungsten
> migration, so it is no more wrong than it was; but treat the four hues as
> asserted rather than proven until a validator covering the colour-vision
> checks exists. `validate-contrast.js` does **not** cover the ramp.

Four slots, not eight: a fifth passing hue doesn't exist at this chroma without
colliding. A fifth series folds into "Other" or gets faceted — never a generated
hue. Dark steps are selected against the dark ground, not flipped. **Assign in
fixed order, never cycled** — colour follows the entity, never its rank.

Most charts here are one series. Provider mix is a magnitude comparison, so it
takes one hue and direct value labels. Reach for the categorical ramp only when
colour genuinely carries identity.

### Rules

- **The accent is a signal, not decoration.** One tungsten action per view. If
  two things are tungsten, neither is the primary action.
- **Colour is used flat.** The only gradients in the system are `.viewing-light`
  (the ambient light source), the `.kelvin-rule` divider, media scrims, and the
  `.developing` shimmer. Never on an interactive surface.
- **Status is always icon + text + colour**, never colour alone.

---

## Type

Three faces, three jobs.

- **Bricolage Grotesque** (`--font-display`) — display only. It has the width
  and weight to hold a full-bleed line. **Never below ~1.75rem**, where its
  character reads as noise instead of voice. Class: `.display-face`.
- **Inter Tight** (`--font-sans`) — the interface. Every word a person reads,
  app and marketing alike.
- **IBM Plex Mono** (`--font-mono`) — everything machine-true: SHA-256 hashes,
  SKUs, model IDs, storage keys, dimensions, timestamps, prices, run IDs.

| Class | Use |
| --- | --- |
| `.display-face` | Headlines. `-0.042em` tracking, line-height 0.98, balanced wrapping. |
| `.kicker` | Section eyebrow: 11px mono, uppercase, `0.16em` tracking. Pair with `.t-accent`. |
| `.tabular` | `tabular-nums` for any figure in a column. |

The signature is **width tension**: headlines tight and heavy against micro-labels
small, wide, and uppercase — like the legend along the edge of a reference card.
That contrast, not a decorative typeface, is what makes the system recognisable.

**The mono/sans split carries meaning:** sans is what we claim, mono is what can
be checked. Keep it honest — don't set marketing copy in mono for texture, and
keep mono values terse. A mono panel is a log line, not a paragraph; anything
long enough to wrap mid-word belongs in sans.

---

## Shape, depth, framing

- `--radius: 0.5rem`. Panels `rounded-xl`, media and controls `rounded-lg`,
  pills `rounded-full`.
- Depth comes from a **hairline first**, elevation second.
- **`.plate`** — the ink-band media motif: inset hairline plus a cast shadow, so
  a photograph reads as an object resting on the table.
- **`.frame` / `.frame-deep`** — the paper-band equivalent, a 1px inset ring so
  assets read as mounted prints. *(Carried forward.)*
- Aspect ratios are locked per style so grids never reflow as assets land:
  `aspect-square` (studio, variant, video), `aspect-[4/5]` (lifestyle, on-model).

---

## Signature motifs

- **`.viewing-light`** — the ambient light source: a tungsten pool low-left, a
  daylight wash high-right. The system's one piece of ambient decoration. Ink
  bands only, and not every one of them.
- **`.kelvin-rule`** — a divider that runs tungsten → neutral → daylight. It
  draws the system's chromatic axis, so it is used where a page turns, not as a
  general separator.
- **The light table** (`components/landing/light-table.tsx`) — the home page's
  centrepiece. A real pack arrives frame by frame, each plate scanned as it
  fills, with the job log naming the model and the frame's **real** SHA-256
  beneath. The proof on the marketing site is checkable, not claimed.
- **The run ledger** (`components/how-it-works/run-ledger.tsx`) — the explanation
  counterpart. One real job entered stage by stage: prose on the left, a machine
  column on the right carrying what a log would record.
- **`.grain`** — the empty plate texture, for a slot waiting on media. **Ink
  bands only:** its dot colour is `--ink-fg`, so on a paper-ground card it
  renders nothing at all in light mode. Use `bg-muted` for a paper empty state.
- **`.developing`** — loading shimmer: a print coming up in the tray, not a grey
  bar. *(Carried forward.)*

---

## Motion

150–550ms, `cubic-bezier(0.2, 0, 0, 1)`. Reveals are **per band, not per
element** — a whole section settling reads calmer than a dozen things arriving
separately. Use `<Reveal>` (`components/landing/section.tsx`), which is
`whileInView` with `once: true`.

Sequenced motion is reserved for things that genuinely are a sequence — the
light table fills in pipeline order. Never animate to fill silence.

`prefers-reduced-motion` is honoured globally in `globals.css`, and every
sequenced component also takes `useReducedMotion()` and renders its finished
state. There is **no animation library beyond framer-motion**.

---

## Components

Primitives live in `frontend/components/ui/`, Radix-backed where behaviour
matters. Composite patterns to reuse rather than re-invent:

| Component | Role |
| --- | --- |
| `Reveal` / `SectionHead` | Band-aware section scaffolding. Start here for any new section. |
| `LightTable` | The home hero's proof surface. |
| `RunLedger` | A pipeline explained as a job record. |
| `LandingHeader` / `LandingFooter` | Public chrome. Serves the whole public surface despite the folder name. |
| `ProvenanceBadge` | The trust signal. Icon + text + colour + mono hash. |
| `ImageTile` | A generated asset as a mounted print, with caption strip. |
| `AssetWorkbench` | The pack grouped by style, slots held for pending frames. |
| `BrandMark` | Four-patch glyph, one patch struck in the verified colour. |
| `StatCard` / `StatGrid` | Metrics in a hairline grid — no card-in-a-card. Figures mono and tabular. |
| `ProviderChart` | A real `<table>`. There is **no chart dependency**; don't add one for a handful of bars. |
| `Field` | Label + control + hint/error, wiring `aria-describedby` and `aria-invalid`. |
| `Card` | `CardTitle` is a **micro-label** (names a region); `CardHeading` names content. Easiest mistake in the codebase. |

---

## Responsiveness *(carried forward — still binding)*

- Flawless 320px → 4K. **Zero horizontal page scroll, zero overflow, zero
  overlap** at any width.
- `min-w-0` on flex/grid children so text truncates instead of pushing layout.
- Tables scroll inside their own container; the page never scrolls sideways.
- Hashes, SKUs and storage keys truncate or wrap — they never force overflow.
- Grids fold stepwise (4→2→1), never all at once.
- A three-column record (rail / prose / machine) collapses to one column below
  `lg`; below that the rail eats the width the prose needs.
- Media grids go two-up on phones, not three — a 120px product photo can't be
  judged, and judging the output is why the panel exists.
- Sticky bars are safe-area aware (`env(safe-area-inset-*)`).

Verify with Playwright at 390 / 820 / 1440, light and dark. Assert
`document.documentElement.scrollWidth <= window.innerWidth`.

---

## Accessibility

WCAG AA. **The contrast law above is the one most easily broken** — re-read it
before adding a coloured label. One focus treatment, defined once on
`:focus-visible`; don't re-style focus per component. 44px minimum touch
targets. Status is never colour alone. Every form control has a label. Generated
media needs descriptive alt text. Sequenced motion always has a static
reduced-motion state.

---

## Content

Words are design material. Name things by what the user controls. Active voice;
a control says what happens when it's used and keeps that name through the flow.
Errors state what happened and what to do. Empty states invite action.

**Never state a number the code doesn't support.** Figures on the marketing site
come from `backend/app/pricing.py` (`_OUTPUTS`, `_UNIT`, `_ETA_SECONDS`) and
model names from `originshot_pipelines/registry.py`. If those change, the copy
changes with them.

**Never illustrate a claim with an asset that contradicts it.** `variant-01.webp`
is a green bottle — the wrong-item fixture from the resolve benchmark — and must
never appear in a grid captioned as one product's pack. Look at the image; the
slot name is not evidence.

**Say what fails.** The how-it-works page names the step with no fallback and
what a partial run costs the user. Hiding failure modes is what makes a tool
read as a demo.

---

## Migration ledger

| Surface | State |
| --- | --- |
| `/` (home) | **Light Table**, complete. |
| `/how-it-works` | **Light Table**, complete. |
| `/about` | **Light Table**, complete. Rebuilt on the band system; the four-icon-card grid is gone, principles now carry the mechanism that enforces them. |
| `/signin` | **Light Table**, complete. Full ink band + `viewing-light`; the Calibration `patch-grid` motif is retired. |
| `/verify` | **Rebuilt.** On `.ink-ground` when signed out. The mode toggle is gone — file drop and hash lookup now coexist, which removed a piece of state and the case where switching modes discarded a result mid-read. |
| `/ledger` | **Rebuilt.** On `.ink-ground` when signed out. The head is a fingerprint block, the entries render as an actual chain (`prev → this` down a spine), and the self-audit is deliberately demoted below the independent-verification block. |
| `/resolve` | **Migrated, bands intentionally not applied** — see "Where bands apply". Display type, kickers and `.t-accent`/`.t-verify` are in; layout stays tool-shaped. |
| Theme toggle | **Removed** from the public header, the app shell and `/signin`. The theme class is still set from the system preference before paint. |
| Type, all surfaces | **Done.** Inter Tight + Bricolage + Plex Mono globally; Archivo retired. |
| Neutrals, all surfaces | **Done.** App semantic tokens mapped onto ink/paper families, both themes. |
| App `--accent` → tungsten | **Done.** The `--warning` collision was resolved in the same change; all 27 `text-accent` sites moved to `.t-accent`; `--accent-text`/`--verify-text` bound at `:root` and `.dark`. |
| `components/marketing/*` | **Deleted.** `/about` was its last consumer; 10 of its 15 components were already dead. |
| App (`/studio`, `/library`, `/analytics`, `/settings`, `/admin`) | Tokens and type current, and every accent surface now resolves through `.t-accent`. Layout is still Calibration-shaped, which is *allowed* by the rule above — but see the caveat below. |

### ⚠ What has not been visually verified

The whole of the above is verified by `tsc`, `next build` (17/17 routes) and
`validate-contrast.js` (25 checks). **None of it has been verified in a
browser.** Playwright is not installed in this repo, so the responsiveness
protocol below — 390 / 820 / 1440, light and dark, asserting
`scrollWidth <= innerWidth` — has *not* been run against these changes.

Two things specifically warrant a screenshot before they are trusted:

- **The signed-in app under tungsten.** `--accent` changed underneath every app
  screen at once. The contrast maths passes, but nobody has looked at
  `/studio`, `/library`, `/analytics`, `/settings` or `/admin` since.
- **The auth card on `/signin`.** A paper `Card` now sits on an ink band, and
  `.band-ink *` repaints every descendant border to `--ink-line`. `Card` sets
  `text-card-foreground` explicitly so the type is safe, but the hairline
  weight against white is unreviewed.
