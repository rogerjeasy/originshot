# OriginShot Design System — "Light Table"

The source of truth for OriginShot's visual language, across the marketing site
and the signed-in app. Tokens live in `frontend/app/globals.css`; this document
explains what they mean and why.

> **Supersedes "Calibration"** (the ColorChecker-patch system, 2026-07-18).
> Calibration's neutrals and type have been retired; several of its rules were
> right and are carried forward verbatim, marked where they appear. The
> migration ledger at the end records exactly what has moved and what hasn't.

**Two layers, one system.** *Light Table* is the colour, type and material
language, and governs everything. **"The Workbench"** (2026-07-20) is the
*layout* language of the signed-in app only — it added no tokens and changed no
colour. Public surfaces are paced by bands; the dashboard is built from regions.
If you are working on a dashboard screen, read **Layout — "the Workbench"**
first.

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

#### The product is dark, permanently

There is no theme system. `dark` is set statically on `<html>`, so the whole
product — public surface and signed-in app alike — runs in the viewing room.
The dashboard background is `#0E1823`; there is no near-white state anywhere.

> An earlier revision of this document argued the opposite (app on paper, ink
> public surface, the sign-in flip as intentional). That was reversed: the flip
> from a dark sign-in page to a near-white dashboard was the wrong first
> impression of the product, and one continuous room beats a defensible
> discontinuity.

**Why the whole `.dark` palette and not just a darker `--background`.** The
light tokens are tuned as a set for a near-white ground. Overriding the
background alone would have left `--card: #FFFFFF`, `--border: #E3E1DB` and
every muted/input value beside it — a combination nothing in the system
validates, and the fastest route to white cards on a dark page. The `.dark` set
is coherent, complete (41 tokens, including the full `--paper-*` family) and
already passes the contrast gate.

`<meta name="color-scheme" content="dark">` ships with it, so the browser's own
form controls, scrollbars and autofill styling stay on the palette instead of
rendering light against every surface.

**The light palette is retained but dormant.** `:root` still carries a complete
light set and `validate-contrast.js` still checks it. Nothing renders it today;
it is kept validated so light mode can be reinstated without re-deriving it.
When reading the gate's output, remember the LIGHT section describes a palette
that is currently unreachable.

**No theme state exists.** The toggle is gone and nothing can write a stored
preference. A one-line script clears any legacy `theme` key: it is dead state,
and leaving it would have stranded a returning visitor on a preference no
control could reach.

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

## Layout — "the Workbench"

Bands pace a page that argues. The signed-in app doesn't argue, it works, so it
has its own layout system. Primitives live in `frontend/components/workbench/`.

**The problem it replaced.** Every dashboard screen was `PageHeader`, then a
`space-y-8` stack of bordered `Card`s. Because a card claims the same weight
wherever it lands, a page of them has no hierarchy: the eye gets nothing for
free, and the surface reads as unrelated widgets on a tinted ground rather than
one instrument.

### Regions, not boxes

A **`Section`** divides with a hairline rule and names itself with a
micro-label — the way a spec sheet or a contact sheet is organised. Continuous
surface, hairline divisions, the content doing the talking.

> **The rule: `Card` is only for genuinely detachable objects** — a media tile,
> a SKU, something you could pick up and move elsewhere. If it can't be picked
> up, it's a `Section`. `Section` takes `framed` for the rare content that
> needs containment; a framed section draws no rule, so a doubled line never
> appears.

**Where `Card` is still correct**, and why the migration deliberately left it:

- `/settings` — the sidebar column is three peer panels. Converting one to a
  borderless `Section` leaves it floating between two bordered neighbours.
- `/admin` operations — a two-column grid of peer panels, same reasoning.

Consistency *within a column* outranks converting everything.

### The pieces

| Primitive | Role |
| --- | --- |
| `Section` | A region: hairline rule + micro-label, optional `state` and `action`. The default. |
| `Step` | A **numbered** stage. See the constraint below. |
| `Lattice` | The shared-hairline grid: N cells share N−1 rules via `gap-px` over `bg-border`, instead of 4N borders doubling at every seam. |
| `Stack` | Page rhythm — `tight` / `normal` / `loose`. One knob, so screens can't drift apart on spacing. |
| `PageToolbar` | The head of every screen: crumbs, title, `action`, `meta`. |
| `RegistrationStrip` / `RegistrationLabel` | The state marker. |
| `CommandPalette` | ⌘K navigation. |

`StatGrid` is now a thin four-column caller of `Lattice`; it stays named so
metric call sites still read as metrics.

### ⚠ Numbering is a claim about order

`Step` renders a numbered marker that becomes a check when `done`. Use it **only
where order is information the reader needs.** Catalog Mode qualifies: there are
no output formats to choose before photos exist, and no run before both are
settled.

Numbered markers on a set of peer regions are decoration pretending to be
structure — that is the single most common way this system gets cheapened. Every
other screen uses unnumbered `Section`s. The number is `aria-hidden` in the
marker and restated as "Step N:" for screen readers, so it is never the only
carrier.

### The registration strip

The app's one signature device, and the counterpart to `.viewing-light` on the
public surface. Printers align colour separations against registration marks; if
the marks line up, the plates are true — which is this product's whole claim, so
the marker **carries state rather than decorating an edge**:

| State | Fill | Means |
| --- | --- | --- |
| `idle` | `--border` | nothing in flight |
| `working` | `--tungsten` | acting — a run in progress |
| `verified` | `--daylight` | checked out |
| `attention` | `--warning` | needs a decision |

It reuses the existing temperature axis and introduces **no third accent**. Only
`working` animates: a travelling highlight, the same gesture as `.developing`,
suppressed entirely under reduced motion rather than merely slowed.

> These are **fill** colours and obey the contrast law below. A strip never
> shares its token with type — `RegistrationLabel` sets its wording in
> `.t-accent` / `.t-verify`, so state is icon **plus** colour **plus** words.

### Page heads

`PageToolbar` replaces the deleted `PageHeader`, which set titles at `text-2xl`
in the interface face — the same treatment as a section heading three levels
down, so nothing signalled the page had changed. The title is now **the one
place the display face appears inside the app**, at the size the system reserves
it for (never below ~1.75rem). Crumbs are mono, because a path in this product is
an address you can check — the face the hashes use.

### Navigation

The rail groups by intent: **Create** (Studio, Catalog Mode), **Inspect**
(Library, Analytics, Verify, Ledger), **Account** (Settings, Admin). Six peer
links put Verify — something you do to finished work — level with Studio, where
work is made. Those two verbs are the product.

One definition renders two shapes: a collapsing icon rail (labels vanish below
`lg`, so the accessible name comes from the element), and a mobile drawer that
keeps its labels. **Each nav landmark takes a distinct accessible name** — three
landmarks all called "Primary" is noise in a landmark list.

`CommandPalette` is hand-rolled on Radix Dialog; **there is no `cmdk`
dependency**, and adding one for a filtered list with roving selection is not
warranted. Matching is substring, not fuzzy: with ~10 destinations, fuzzy mostly
produces confident wrong answers. Selection indexes the **grouped render order**,
not the filter order — they diverge whenever a filter interleaves groups, and
indexing the wrong one opens a different row than the one highlighted.

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
- **The registration strip** — the signed-in app's signature device, the
  counterpart to `.viewing-light` on the public surface. Its `working` animation
  is deliberately the same travelling-exposure gesture as `.developing`, so a
  strip beside a loading placeholder reads as one system rather than two
  effects. Full contract under **Layout — "the Workbench"**.

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
| `StatCard` / `StatGrid` | Metrics in a hairline grid — no card-in-a-card. Figures mono and tabular. `StatGrid` is `Lattice` at four columns. |
| `ProviderChart` | A real `<table>`. There is **no chart dependency**; don't add one for a handful of bars. |
| `Field` | Label + control + hint/error, wiring `aria-describedby` and `aria-invalid`. |
| `SkuCard` | A product tile. Deliberately **has no thumbnail**: `Sku` carries `original_sha256` but no URL, so one would cost a fetch per tile to render decoration. |
| `Card` | `CardTitle` is a **micro-label** (names a region); `CardHeading` names content. Easiest mistake in the codebase. **Reach for `Section` first** — see Layout. |

For app layout — `Section`, `Step`, `Lattice`, `Stack`, `PageToolbar`,
`RegistrationStrip`, `CommandPalette` — see **Layout — "the Workbench"** above.
Start there for any new dashboard screen.

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
| Theme | **Dark only.** `dark` is set statically on `<html>`; the toggle and `theme-toggle.tsx` are deleted, and no theme state exists. The light palette is retained and still gated, but dormant. |
| App surfaces under dark | Every app screen now renders on `.dark` rather than following a preference. Tokens are coherent and gated, but **no app screen has been opened in a browser since** — see the caveat below. |
| Type, all surfaces | **Done.** Inter Tight + Bricolage + Plex Mono globally; Archivo retired. |
| Neutrals, all surfaces | **Done.** App semantic tokens mapped onto ink/paper families, both themes. |
| App `--accent` → tungsten | **Done.** The `--warning` collision was resolved in the same change; all 27 `text-accent` sites moved to `.t-accent`; `--accent-text`/`--verify-text` bound at `:root` and `.dark`. |
| `components/marketing/*` | **Deleted.** `/about` was its last consumer; 10 of its 15 components were already dead. |
| App (`/studio`, `/studio/[skuId]`, `/studio/catalog`, `/library`, `/analytics`, `/settings`, `/admin`) | **Rebuilt on the Workbench.** The `PageHeader` + stacked-`Card` rhythm is gone; regions are `Section`s, Catalog Mode is a numbered `Step` sequence, page heads are `PageToolbar`. Token layer untouched — no colour, type or contrast change, gate still 25/25. Logic untouched: `jobId`-keyed polling, the loading-versus-empty distinction and the blob export are byte-identical. |
| App shell | **Rebuilt.** Nav grouped Create / Inspect / Account, one definition rendering rail and drawer, ⌘K palette. Auth enforcement unchanged — still no dev bypass. |
| `components/page-header.tsx` | **Deleted.** Superseded by `PageToolbar`; zero consumers remained. |
| Library / Analytics detail | Library gained visible legends on its filter axes (previously distinguishable only by `aria-label`) and a clear-filters affordance it never had. Analytics names its two stat rows, so the split between them carries information. |

### ⚠ What has not been visually verified

The whole of the above is verified by `tsc`, `next build` (17/17 routes) and
`validate-contrast.js` (25 checks). **None of it has been verified in a
browser.** Playwright is not installed in this repo, so the responsiveness
protocol below — 390 / 820 / 1440, light and dark, asserting
`scrollWidth <= innerWidth` — has *not* been run against these changes.

Three things specifically warrant a screenshot before they are trusted:

- **The Workbench layout, everywhere.** The 2026-07-20 rewrite changed the
  structure of all eight dashboard screens at once. It is verified by `tsc`,
  `next build` (17/17) and the contrast gate only. Nothing about "does a
  borderless region read as a region, or as content that lost its container"
  can be settled by a build — that is exactly the question the rewrite is
  betting on, and it is unanswered. Start with `/studio/[skuId]` and
  `/studio/catalog`, which took the most structural change.
- **The signed-in app under tungsten.** `--accent` changed underneath every app
  screen at once. The contrast maths passes, but nobody has looked at
  `/studio`, `/library`, `/analytics`, `/settings` or `/admin` since.
- **The auth card on `/signin`.** A paper `Card` now sits on an ink band, and
  `.band-ink *` repaints every descendant border to `--ink-line`. `Card` sets
  `text-card-foreground` explicitly so the type is safe, but the hairline
  weight against white is unreviewed.

Note the protocol below says "light and dark". **The product is dark-only** —
there is one theme to check, not two. The light palette is dormant and gated;
see "The product is dark, permanently".
