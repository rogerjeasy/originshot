#!/usr/bin/env node
/**
 * Contrast gate for the "Light Table" token set.
 *
 * Reads the real values out of app/globals.css rather than restating them, so
 * this can't quietly drift from what ships. Run it after touching any colour
 * token:
 *
 *   node scripts/validate-contrast.js
 *
 * Exits non-zero on any AA failure, so it works as a pre-commit or CI gate.
 *
 * Why this exists: --tungsten and --daylight are light colours. As *text* on
 * paper they measure 2.00:1 and 2.18:1. That shipped once and had to be undone
 * across six components, and again when --accent moved to tungsten and 27
 * `text-accent` sites would have inherited the same failure. The rule the
 * checker enforces is the one in docs/DESIGN_SYSTEM.md: full-chroma tokens are
 * fills, .t-accent / .t-verify are type.
 */
const fs = require("fs");
const path = require("path");

const CSS = fs.readFileSync(path.join(__dirname, "..", "app", "globals.css"), "utf8");

/**
 * Pull `--name: #rrggbb` out of every block opened by `scope`.
 *
 * There is more than one of each: the app's semantic tokens sit in the first
 * :root / .dark pair, the Light Table primitives (ink, paper, tungsten,
 * daylight) in a second pair further down. Reading only the first block silently
 * loses half the system, so all of them are merged in source order — later
 * definitions win, exactly as the cascade would resolve them.
 */
function tokens(scope) {
  const out = {};
  let from = 0;
  let found = false;
  for (;;) {
    const start = CSS.indexOf(scope, from);
    if (start === -1) break;
    found = true;
    // Blocks are top-level, so the first newline-anchored `}` closes them.
    const end = CSS.indexOf("\n}", start);
    for (const m of CSS.slice(start, end).matchAll(/--([a-z0-9-]+):\s*(#[0-9a-fA-F]{6})\b/g)) {
      out[m[1]] = m[2].toLowerCase();
    }
    from = end;
  }
  if (!found) throw new Error(`scope not found: ${scope}`);
  return out;
}

/** Fail loudly on a typo'd token name rather than reporting NaN as a pass. */
function need(set, name, which) {
  const v = set[name];
  if (!v) throw new Error(`--${name} not found in ${which}`);
  return v;
}

const hex = (h) => [1, 3, 5].map((i) => parseInt(h.substr(i, 2), 16));
const lin = (v) => {
  v /= 255;
  return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4);
};
const L = (h) => {
  const c = hex(h).map(lin);
  return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2];
};
const CR = (a, b) => {
  const x = L(a), y = L(b);
  return (Math.max(x, y) + 0.05) / (Math.min(x, y) + 0.05);
};

/** CIELAB ΔE — used to keep hues that mean different things apart. */
function lab(h) {
  let [r, g, b] = hex(h).map(lin);
  let X = (0.4124 * r + 0.3576 * g + 0.1805 * b) / 0.95047;
  let Y = 0.2126 * r + 0.7152 * g + 0.0722 * b;
  let Z = (0.0193 * r + 0.1192 * g + 0.9505 * b) / 1.08883;
  const f = (t) => (t > 0.008856 ? Math.cbrt(t) : 7.787 * t + 16 / 116);
  [X, Y, Z] = [f(X), f(Y), f(Z)];
  return [116 * Y - 16, 500 * (X - Y), 200 * (Y - Z)];
}
const dE = (a, b) => {
  const p = lab(a), q = lab(b);
  return Math.hypot(p[0] - q[0], p[1] - q[1], p[2] - q[2]);
};

const light = tokens(":root {");
const dark = tokens(".dark {");

let failures = 0;
const ratio = (label, fg, bg, min = 4.5) => {
  const r = CR(fg, bg);
  const ok = r >= min;
  if (!ok) failures++;
  console.log(`  ${ok ? "pass" : "FAIL"}  ${r.toFixed(2).padStart(5)}  ${label}`);
};
const apart = (label, a, b, min = 15) => {
  const d = dE(a, b);
  const ok = d >= min;
  if (!ok) failures++;
  console.log(`  ${ok ? "pass" : "FAIL"}  ΔE ${d.toFixed(1).padStart(4)}  ${label}`);
};

const l = (n) => need(light, n, ":root");
const d = (n) => need(dark, n, ".dark");

// Surfaces. --ink is theme-independent; --paper is redefined in dark, where the
// paper band becomes a second, lighter room rather than flipping to white.
const PAPER = l("paper");
const INK = l("ink");

console.log("\nLIGHT — type on paper");
ratio(".t-accent  → --tungsten-ink", l("tungsten-ink"), PAPER);
ratio(".t-verify  → --daylight-ink", l("daylight-ink"), PAPER);
ratio("--muted-foreground", l("muted-foreground"), PAPER);
ratio("--warning", l("warning"), PAPER);
ratio("--danger", l("danger"), PAPER);
ratio("--verified", l("verified"), PAPER);
ratio("--info", l("info"), PAPER);
ratio("--warning on --warning-surface", l("warning"), l("warning-surface"));
// `.ink-ground .surface` puts a paper panel on the ink ground and shifts the
// muted token back to --paper-mute, so the pairing is against --card, not paper.
ratio(".surface muted text on --card", l("paper-mute"), l("card"));
ratio(".surface .t-accent on --card", l("tungsten-ink"), l("card"));

console.log("LIGHT — the accent as a fill (never as type)");
ratio("--accent-foreground on --accent", l("accent-foreground"), l("accent"));
ratio("--accent-foreground on --accent-hover", l("accent-foreground"), l("accent-hover"));
ratio("--ring on paper (non-text, 3:1)", l("ring"), PAPER, 3);

console.log("LIGHT — hues that must not be confused");
apart("--warning vs --tungsten-ink (the primary action)", l("warning"), l("tungsten-ink"));
apart("--warning vs --danger", l("warning"), l("danger"));

console.log("\nDARK — type on ink");
ratio(".t-accent  → --tungsten", l("tungsten"), INK);
ratio(".t-verify  → --daylight", l("daylight"), INK);
ratio("--muted-foreground", d("muted-foreground"), INK);
ratio("--warning", d("warning"), INK);
ratio("--danger", d("danger"), INK);
ratio("--verified", d("verified"), INK);
ratio("--info", d("info"), INK);
ratio("--warning on --warning-surface", d("warning"), d("warning-surface"));
ratio(".t-accent on the dark paper band", l("tungsten"), d("paper"));
// --ink-mute is theme-independent: defined once in :root, not redefined in .dark.
ratio(".ink-ground muted text on ink", l("ink-mute"), INK);
ratio(".surface muted text on --card", d("paper-mute"), d("card"));
ratio(".surface .t-accent on --card", l("tungsten"), d("card"));

console.log("DARK — the accent as a fill");
ratio("--accent-foreground on --accent", d("accent-foreground"), d("accent"));

console.log("DARK — hues that must not be confused");
apart("--warning vs --tungsten (the primary action)", d("warning"), l("tungsten"));
apart("--warning vs --danger", d("warning"), d("danger"));

console.log(
  failures ? `\n${failures} failure(s).\n` : "\nAll pairings pass AA and stay perceptually apart.\n",
);
process.exit(failures ? 1 : 0);
