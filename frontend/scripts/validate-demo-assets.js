#!/usr/bin/env node
/**
 * Integrity gate for the marketing site's demo assets.
 *
 *   node scripts/validate-demo-assets.js
 *
 * Exits non-zero on any failure, so it works as a pre-commit or CI gate.
 *
 * Why this exists: the landing page prints real SHA-256 hashes and invites the
 * visitor to check them — "Check this hash yourself" is a literal button. That
 * makes every hash on the page load-bearing in a way ordinary marketing copy is
 * not, and it shipped broken. Four of the fifteen assets had had their database
 * rows deleted, so the flagship hash on the landing page answered "No record
 * found for this hash", and several others carried no provenance manifest at all
 * while the page asserted `content_bound: true` beside them. Nothing caught it,
 * because nothing was looking.
 *
 * Two halves of the guard, split by what each can check offline:
 *
 *   * `scripts/sync-demo-assets.py` (repo root) validates each pick against the
 *     LIVE /verify API at sync time and refuses to write a hash that does not
 *     resolve. That is the check that needs the network.
 *   * this script enforces everything checkable from the tree alone — that the
 *     slots the pages reference actually exist, that the files they point at are
 *     on disk, and that the hashes are well-formed. That is the check that can
 *     run in CI on every commit.
 */
const fs = require("fs");
const path = require("path");

const FRONTEND = path.join(__dirname, "..");
const read = (p) => fs.readFileSync(path.join(FRONTEND, p), "utf8");

const failures = [];
const fail = (msg) => failures.push(msg);

// ── Parse the generated module ───────────────────────────────────────────────
const assetsSrc = read("lib/demo-assets.ts");
const assets = [...assetsSrc.matchAll(/\{\s*slot:\s*"([^"]+)"[^}]*?src:\s*"([^"]+)"[^}]*?sha:\s*"([^"]*)"[^}]*?\}/g)]
  .map(([, slot, src, sha]) => ({ slot, src, sha }));

if (assets.length === 0) {
  fail("lib/demo-assets.ts parsed to zero assets — the generator's shape changed.");
}

const bySlot = new Map(assets.map((a) => [a.slot, a]));
if (bySlot.size !== assets.length) {
  fail(`duplicate slot names in demo-assets.ts (${assets.length} entries, ${bySlot.size} unique)`);
}

// ── Every hash must be a full SHA-256 ────────────────────────────────────────
// A truncated hash still *looks* right on the page but /verify resolves by exact
// match only, so a 16-char prefix renders a dead "check this yourself" link.
for (const a of assets) {
  if (!/^[0-9a-f]{64}$/.test(a.sha)) {
    fail(`${a.slot}: sha is not 64 lowercase hex chars ("${a.sha.slice(0, 24)}…")`);
  }
}

// ── Every referenced file must actually be on disk ───────────────────────────
for (const a of assets) {
  const file = path.join(FRONTEND, "public", a.src.replace(/^\//, ""));
  if (!fs.existsSync(file)) fail(`${a.slot}: src ${a.src} does not exist in public/`);
}

// ── Every slot a page addresses must exist ───────────────────────────────────
// `framesFor()` filters unknown slots out silently, so a retired slot degrades
// into a quietly empty gallery group rather than an error. This is that error.
const packSrc = read("lib/pack.ts");
const referenced = new Set();

for (const [, id, body] of packSrc.matchAll(/id:\s*"([^"]+)"[\s\S]*?slots:\s*\[([^\]]*)\]/g)) {
  const slots = [...body.matchAll(/"([^"]+)"/g)].map((m) => m[1]);
  if (slots.length === 0) fail(`pack.ts group "${id}" lists no slots`);
  for (const s of slots) {
    referenced.add(s);
    if (!bySlot.has(s)) fail(`pack.ts group "${id}" references unknown slot "${s}"`);
  }
}

const seqSrc = read("components/landing/light-table.tsx");
const seqBlock = seqSrc.match(/const SEQUENCE = \[([\s\S]*?)\] as const;/);
if (!seqBlock) {
  fail("light-table.tsx: could not find the SEQUENCE array");
} else {
  for (const [, slot] of seqBlock[1].matchAll(/slot:\s*"([^"]+)"/g)) {
    referenced.add(slot);
    if (!bySlot.has(slot)) fail(`light-table.tsx SEQUENCE references unknown slot "${slot}"`);
  }
}

// The evidence card hardcodes which slot it features; if that slot goes away it
// falls back to DEMO_ASSETS[0] and silently shows a different frame's record.
const evidenceSrc = read("components/landing/evidence.tsx");
const featured = evidenceSrc.match(/a\.slot === "([^"]+)"/);
if (featured) {
  referenced.add(featured[1]);
  if (!bySlot.has(featured[1])) {
    fail(`evidence.tsx features unknown slot "${featured[1]}" — the card would fall back silently`);
  }
}

// ── Orphans are a warning, not a failure ─────────────────────────────────────
// An asset nobody shows costs a little bandwidth in the repo and nothing else.
const orphans = assets.map((a) => a.slot).filter((s) => !referenced.has(s));

// ── Report ───────────────────────────────────────────────────────────────────
console.log(`demo assets: ${assets.length} entries, ${referenced.size} referenced by a page`);
if (orphans.length) console.log(`  note: ${orphans.length} unreferenced (${orphans.join(", ")})`);

if (failures.length) {
  console.error(`\n${failures.length} failure(s):`);
  for (const f of failures) console.error(`  ✗ ${f}`);
  console.error(
    "\nRegenerate with `python scripts/sync-demo-assets.py` from the repo root — it\n" +
    "validates every pick against the live /verify API before writing."
  );
  process.exit(1);
}
console.log("✓ every referenced slot exists, every hash is well-formed, every file is present");
