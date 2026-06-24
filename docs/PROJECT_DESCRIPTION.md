# ListSnap — Project Description

> **One phone photo in. A full marketplace-ready catalog out — with cryptographic proof of what's real and what's AI.**

ListSnap turns a single snapshot of a product into studio-quality white-background shots, lifestyle scenes, on-model images, color/angle variants, and a short product video — then stores every asset on Backblaze B2 with an embedded, verifiable provenance manifest that doubles as AI-disclosure compliance.

- **Built for:** Backblaze Generative Media Hackathon ("Build with Genblaze on B2")
- **Submission deadline:** August 3, 2026, 5:00 PM EDT
- **Core stack:** Genblaze SDK · Backblaze B2 · GMI Cloud (+ multi-provider fallback) · Firebase (Auth + Firestore) · FastAPI on Render · Next.js + Tailwind + shadcn/ui on Vercel
- **Companion docs:** [`BUILD_PLAN.md`](./BUILD_PLAN.md) — end-to-end engineering plan · [`SECURITY.md`](./SECURITY.md) — security & privacy design (**mandatory**)

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [The Problem](#2-the-problem)
3. [Target Users](#3-target-users)
4. [Solution Overview](#4-solution-overview)
5. [Core Features](#5-core-features)
6. [The Provenance Advantage](#6-the-provenance-advantage)
7. [Why Backblaze B2 + Genblaze](#7-why-backblaze-b2--genblaze)
8. [How ListSnap Maps to the Judging Criteria](#8-how-listsnap-maps-to-the-judging-criteria)
9. [Competitive Landscape & Differentiation](#9-competitive-landscape--differentiation)
10. [Business Model](#10-business-model)
11. [Scope: MVP vs. Stretch](#11-scope-mvp-vs-stretch)
12. [Success Metrics](#12-success-metrics)
13. [Risks & Mitigations](#13-risks--mitigations)
14. [Providers & Models](#14-providers--models)

---

## 1. Executive Summary

Online sellers live or die by their product images, yet shooting good photos is the single most repetitive, expensive, and skill-gated chore in their day. ListSnap removes it. A seller uploads **one** ordinary phone photo of a product and receives, in minutes, a complete, marketplace-formatted image pack plus a short product video — all generated through orchestrated Genblaze pipelines, all stored and organized on Backblaze B2.

What makes ListSnap a *winning* hackathon entry rather than another "AI image tool" is the **provenance layer**. Every generated file carries a SHA-256–verified Genblaze manifest embedded directly into the media and persisted to B2. That single design choice turns a feature into a defensible product:

- It is **automatic AI-disclosure compliance** for marketplaces and the EU AI Act.
- It provides **proof of authenticity** — which pixels are the real product vs. AI-enhanced.
- It enables **one-click reproducibility** — any asset can be regenerated or audited from its manifest.

ListSnap therefore hits all four judging criteria at full strength: it solves a real, daily, mass-market problem (Real-World Utility), it is architected like a real SaaS with multi-provider fallback (Production Readiness), it uses B2 as a content-addressable, deduplicated, analytics-backed asset library (B2 Storage & Data Orchestration), and it leans on Genblaze for genuinely multi-step, chained, provenance-stamped generation (Genblaze Usage).

---

## 2. The Problem

**Product photography is the highest-leverage and most-hated task in e-commerce.**

Listings with clean, varied, professional imagery convert dramatically better than listings with a single dim phone photo — buyers can't touch the product, so the image *is* the product. Yet getting those images is painful:

- **Cost.** Professional product photography runs roughly **$25–$150 per product** for basic studio shots and far more for lifestyle or on-model sets and video. For a seller with hundreds of SKUs, that's prohibitive.
- **Time & skill.** Lightboxes, backdrops, lighting, editing in Photoshop, background removal, resizing per marketplace — it's hours of fiddly work per product, repeated every time inventory changes.
- **Format churn.** Amazon wants a pure-white background at specific pixel dimensions; Etsy rewards lifestyle context; Shopify themes want consistent aspect ratios; eBay, Poshmark, Depop, and social each differ. Sellers re-edit the same product endlessly.
- **Variants explode the work.** Five colors × three angles × two backgrounds = 30 images for one product.
- **A new compliance burden is arriving.** Marketplaces and regulators (e.g., the EU AI Act's transparency rules) increasingly require **disclosing AI-generated or AI-altered imagery**. Today sellers either ignore this (risk) or have no clean way to comply.

**Market size (approximate, illustrative).** The addressable base is enormous and these sellers face this problem *daily*:

| Channel | Approx. sellers |
|---|---|
| eBay | ~18M+ |
| Etsy | ~9M active |
| Shopify merchants | ~4–5M stores |
| Amazon third-party (active) | ~2M |
| Mercari / Poshmark / Depop / Vinted / FB Marketplace | Tens of millions of casual sellers |

> Figures are rounded public estimates for sizing only. Even a fraction of this base is a multi-million-user market, and listing/refreshing products is a recurring, high-frequency activity — exactly the "real daily, boring problem" profile.

**Current alternatives and why they fall short.** Tools like Photoroom, Pebblely, Claid, and various "AI product photo" apps do background removal and scene generation well, but they: (a) treat each image as a one-off rather than orchestrating a full multi-output catalog + video pipeline, (b) provide **no provenance or AI-disclosure trail**, and (c) lock assets in their own storage with no cost-transparent, durable, portable library. ListSnap is positioned exactly in those gaps.

---

## 3. Target Users

**Primary persona — "Maya, the multi-SKU marketplace seller."** Runs an Etsy + Shopify shop with 150 products, photographs new inventory weekly on her phone, and burns evenings editing images for each channel. She needs *volume, consistency, and speed*, and she's heard marketplaces are starting to ask about AI imagery.

**Secondary persona — "Sam, the Amazon FBA operator."** Manages dozens of SKUs, cares about strict Amazon image compliance (pure white background, fill ratio), wants on-model and infographic-style shots, and wants to A/B test main images. Provenance disclosure protects his account from policy strikes.

**Tertiary persona — "Casey, the casual reseller."** Sells used and handmade items on eBay/Depop/FB Marketplace. Won't pay for a photographer ever. Wants a "make this look good and write the listing" button. Trust/authenticity matters to buyers of used goods.

**Buyer-side beneficiary.** Shoppers benefit from honest "AI-enhanced" labels — ListSnap's verify page lets a marketplace or a buyer confirm what's authentic.

---

## 4. Solution Overview

ListSnap is a web app with a simple core loop:

```
1. CREATE a product (SKU) → 2. UPLOAD one (or a few) phone photos
        ↓
3. PICK output styles + marketplace presets (or "do everything")
        ↓
4. GENERATE  ──►  Genblaze pipelines fan out across providers
        ↓
5. REVIEW the pack: studio · lifestyle · on-model · variants · video
        ↓
6. EXPORT per-marketplace  +  every file carries an embedded provenance manifest
        ↓
7. LIBRARY on B2: content-addressable, deduplicated, searchable, with a cost/usage dashboard
```

Everything generated is durable, organized by SKU, deduplicated, and provably attributed. The original upload is hash-anchored as the "authentic source," and each generated asset's manifest links back to it (`parent_run_id` lineage), so the system always knows the difference between the real product and an AI rendition of it.

---

## 5. Core Features

### A. Capture & Ingest
- **One-photo input.** Drag-drop or mobile capture of a single product photo; optional multi-angle upload.
- **Authentic-source anchoring.** On upload, ListSnap computes the SHA-256, stores the original on B2 as an immutable "authentic" asset, and marks it `is_authentic = true` (no AI). This is the trust anchor for all downstream provenance.
- **Auto product analysis.** A vision/chat model (e.g., Gemini/Qwen-VL via GMI Cloud) detects product type, dominant colors, and suggested categories to drive smart defaults.

### B. Generation Studio (the heart of the app)
Each is an orchestrated Genblaze pipeline (see [`BUILD_PLAN.md`](./BUILD_PLAN.md) §7 for code):

- **Studio shots.** Clean, pure-white-background, evenly relit product images (Amazon-ready). Background removal + relight + framing.
- **Lifestyle scenes.** Product placed in believable contexts (kitchen counter, wooden desk, marble bathroom, outdoor café). Multiple scenes per run via batch fan-out.
- **On-model shots.** For apparel/accessories/wearables — product shown on a person, with diversity options.
- **Variant fan-out.** Auto-generate color, angle, and background variations from one base — the "30 images from one photo" feature.
- **Product video.** Chained **image-to-video** (best hero image → 5-second clip with subtle camera motion) via Kling/Seedance, optionally with generated ambient SFX/music muxed in.
- **Infographic / hero-text overlays (stretch).** Feature callouts and size/spec badges.

### C. Marketplace Presets
- One-click formatting to **Amazon, Etsy, Shopify, eBay, and Social (1:1 / 4:5 / 16:9)** — correct dimensions, background rules, fill ratios, and file specs.
- A single generation run can emit a per-marketplace export pack.

### D. Provenance & Compliance *(the differentiator — see §6)*
- Embedded, verifiable manifest in every generated file.
- Auto-generated **AI-disclosure statement** per asset and per export pack.
- **Authentic vs. AI** badging across the UI.
- Public **/verify** page: drop in a file or asset ID → confirm integrity, see lineage.

### E. Asset Library on B2
- **Content-addressable storage** with automatic deduplication (re-uploaded originals, shared scene plates, identical regenerations never pay twice).
- Organized and searchable by SKU, style, marketplace, and date.
- Durable, portable, low-cost — the seller's media is theirs, not trapped in a black box.

### F. Analytics & Cost Dashboard
- Powered by Genblaze's **ParquetSink** metadata export.
- Shows assets generated, storage used, **dedup savings**, estimated generation cost per SKU, provider mix, and success/fallback rates.
- Turns "data orchestration" from a buzzword into a visible, judge-friendly screen.

### G. Brand Kit & Consistency
- Save brand colors, preferred scene styles, logo, and lighting; reuse across SKUs for a consistent shop look.
- **AgentLoop**-based iterative refinement to nudge outputs toward brand guidelines.

### H. Export & Publish
- Download per-marketplace ZIP packs (images + video + `disclosure.txt` + sidecar manifests).
- Stretch: direct push to Shopify/Etsy via their APIs.

### I. Team & History (stretch)
- Multiple seats, shared library, and full run history with one-click **replay** (regenerate any past asset from its manifest).

### J. Security, Privacy & Trust (mandatory, not optional)
- **Authenticated by default** via Firebase Authentication; every API request is verified server-side and scoped to the signed-in user.
- **Strict per-user data isolation** — a seller can only ever see and touch their own SKUs, assets, and jobs (enforced in the backend *and* in Firestore Security Rules).
- **Secrets never leave the server** — provider and B2 keys live only in backend secret storage; the browser never sees them.
- **Safe uploads** — file-type and size validation, EXIF/GPS metadata stripping (privacy), and content moderation on inputs and generated outputs.
- **Denial-of-wallet protection** — per-user generation quotas, rate limits, and spend caps, because every generation costs real money.
- **Privacy & compliance** — data export/deletion (GDPR/CCPA), least-privilege access, and AI-content disclosure baked into provenance.
- Full design and threat model in [`SECURITY.md`](./SECURITY.md).

---

## 6. The Provenance Advantage

This is what separates ListSnap from every other AI product-photo tool and what aligns it with the feature Backblaze built Genblaze around.

**What we do.** Every generated image and video is stamped with a Genblaze **Manifest** — a canonical, SHA-256–verified record of provider, model, prompt, parameters, timestamps, and parent lineage — *embedded directly into the file* (`.png`, `.webp`, `.jpeg`, `.mp4`) and also persisted to B2 as a sidecar. Original uploads are hash-anchored as authentic. Generated assets carry `parent_run_id` lineage back to that original.

**Why it matters — three concrete payoffs:**

1. **Automatic AI-disclosure compliance.** Marketplaces and the EU AI Act increasingly require labeling AI-generated/altered media. ListSnap produces the disclosure automatically and makes it *verifiable*, not just a checkbox. This is a genuine, emerging legal need — strong "Real-World Utility."
2. **Proof of authenticity / anti-fraud.** Buyers of used or high-value goods (and the marketplaces policing them) can confirm which image is the unedited real product and which is an enhancement. The manifest distinguishes "authentic" from "AI-derived" cryptographically.
3. **Reproducibility & audit.** Because each manifest captures the full run, any asset can be **replayed** (`genblaze replay`) — regenerated in a new size/style, or audited months later. Sellers and platforms get a tamper-evident trail.

**Demo moment.** In the 3-minute video we run `genblaze verify` on a downloaded file live, show the embedded manifest, and toggle the "authentic vs. AI" badge — a memorable, criteria-maxing beat almost no competing entry will have.

---

## 7. Why Backblaze B2 + Genblaze

**Genblaze is the orchestration brain.** ListSnap is inherently multi-step and multi-provider: background removal → relight → scene compositing → variant fan-out → image-to-video → SFX mux → provenance embed. Genblaze's `Pipeline`/`Step`/`chain=True`, fallback chains, batch runners, lineage, and manifests express this cleanly and reliably. We are not bolting one API call onto a UI — we're orchestrating a real media pipeline, which is exactly the "meaningful Genblaze integration" the judges want.

**B2 is the durable, cost-smart media backbone.** An asset-heavy app generates a lot of large files. B2 gives us:
- **Low storage + generous egress economics**, so a media library at scale is actually affordable (a real cost story for sellers).
- **Content-addressable layout + dedup** via Genblaze's `KeyStrategy.CONTENT_ADDRESSABLE`, so identical bytes are stored once.
- **Parquet analytics export** for the dashboard.
- **Durable, portable ownership** of the seller's catalog.

Together they let a small team ship something that looks and behaves like a production SaaS within the hackathon window.

---

## 8. How ListSnap Maps to the Judging Criteria

| Judging criterion | How ListSnap nails it |
|---|---|
| **Real-World Utility** | Solves the #1 daily, paid-for pain of tens of millions of sellers; provenance addresses a real emerging compliance need. People pay for this category *today*. |
| **Production Readiness** | **Firebase Auth + strict per-user isolation**, multi-provider **fallback chains** (provider outage ≠ failed job), retries, async job workers, live deployed URL (Render + Vercel), secret management, rate limits/quotas, robust error handling, and per-marketplace correctness. Full security design in [`SECURITY.md`](./SECURITY.md). |
| **B2 Storage & Data Orchestration** | B2 as a **content-addressable, deduplicated** asset library; embedded + sidecar manifests on B2; **ParquetSink** metadata feeding a live cost/usage dashboard. |
| **Genblaze Usage** | Genuinely **multi-step, chained** pipelines; batch variant fan-out; image-to-video chaining; lineage (`from_result`); **provenance embed/verify/replay**; AgentLoop refinement. |

---

## 9. Competitive Landscape & Differentiation

| Capability | Photoroom / Pebblely / Claid (typical) | **ListSnap** |
|---|---|---|
| Background removal & scenes | ✅ | ✅ |
| Full multi-output catalog in one run | ◻️ partial | ✅ orchestrated pipeline |
| Image-to-video product clip | ◻️ rare | ✅ chained |
| Per-marketplace presets | ◻️ some | ✅ |
| **Provenance / AI-disclosure** | ❌ | ✅ **embedded + verifiable** |
| **Durable, dedup, cost-transparent library** | ❌ (locked-in) | ✅ **on B2** |
| Reproducible / replayable assets | ❌ | ✅ |

**Our wedge:** the only product-photo tool that is *trustworthy and auditable by design* and gives the seller a durable, cost-transparent library they own. That's a story judges remember and a moat competitors can't quickly copy.

---

## 10. Business Model

- **Freemium credits.** N free generations/month; paid tiers by generation volume and resolution/video.
- **Per-marketplace export packs** as a premium feature.
- **Storage tiers** for large catalogs (passing through B2's low cost with margin).
- **Compliance/Pro tier:** verified provenance + audit exports for businesses that need disclosure at scale.
- **API / white-label (later):** offer the pipeline to marketplaces and PIM/e-commerce platforms directly.

This shows judges a credible path beyond the demo — reinforcing "Real-World Utility" and "Production Readiness."

---

## 11. Scope: MVP vs. Stretch

**MVP (must ship for submission):**
- One-photo upload + SKU model.
- Studio + lifestyle + variant fan-out (images) and image-to-video (one 5-sec clip).
- B2 content-addressable storage; embedded + sidecar manifests; `/verify` page.
- Multi-provider fallback on at least the image step.
- Analytics dashboard from ParquetSink (assets, storage, dedup savings, cost).
- Live deployed URL + repo + 3-min demo.

**Stretch (if time allows):**
- On-model shots, infographic overlays, brand kit, AgentLoop refinement.
- SFX/music muxed into video.
- Direct marketplace publishing (Shopify/Etsy).
- Team seats, run history with one-click replay.

> Build order, week-by-week, is in [`BUILD_PLAN.md`](./BUILD_PLAN.md) §13.

---

## 12. Success Metrics

**Product KPIs (post-hackathon framing):**
- Time-to-catalog: < 5 minutes from one photo to a full export pack.
- Cost per complete SKU pack vs. ~$25–$150 photographer baseline.
- % of assets carrying a verifiable manifest (target: 100%).
- Dedup savings ratio surfaced in the dashboard.

**Hackathon "win" metrics:**
- All four judging criteria visibly demonstrated in the 3-min video.
- Live URL works on judges' first try (reliability via fallbacks).
- A memorable provenance demo beat (`genblaze verify` on screen).

---

## 13. Risks & Mitigations

| Risk | Mitigation |
|---|---|
| A generation provider is slow/down during judging | Genblaze **fallback chains** + retries; pre-warm/cache a demo SKU; graceful UI states. |
| Video generation latency hurts the live demo | Generate the demo video ahead of time; show async job UI; keep clips short (5s). |
| Product fidelity (AI changes the actual item) | Use image-editing/reference-preserving models; keep the **authentic original** prominent; provenance makes edits transparent. |
| Cost of generations during testing | Cache aggressively (content-addressable), cap resolution in dev, use credits/cheaper models for non-hero outputs. |
| SDK/model API drift | Pin versions; isolate provider/model IDs in config; verify against the live SDK during Week 1 (see build plan). |
| Scope creep | Strict MVP cut line above; stretch features only after the end-to-end path is green. |

---

## 14. Providers & Models

*(Submission requires listing providers/models used. Final list locked in Week 1 against the installed SDK; this is the planned set.)*

- **Image generation / editing:** GMI Cloud — Seedream, FLUX, Gemini image; fallbacks via OpenAI `gpt-image` and/or Google Imagen.
- **Image-to-video:** GMI Cloud — Kling (`Kling-Image2Video-V2.1-Master`), Seedance; fallback Luma/Runway.
- **Vision/analysis & copy:** GMI Cloud chat models (Qwen-VL / Llama / DeepSeek) or Gemini for product detection and listing text.
- **Audio (stretch, video SFX/music):** ElevenLabs SFX / Stability Audio.
- **Orchestration & provenance:** Genblaze SDK (`Pipeline`, `Step`, `Manifest`, `ObjectStorageSink`, `ParquetSink`).
- **Storage:** Backblaze B2 via `S3StorageBackend.for_backblaze(...)`.
- **Auth & database:** Firebase Authentication + Cloud Firestore.
- **Hosting:** FastAPI on Render (web service + worker + Key Value/Redis); Next.js (Tailwind + shadcn/ui) on Vercel.

---

*See [`BUILD_PLAN.md`](./BUILD_PLAN.md) for architecture, pipeline code, API design, the 6-week schedule, the demo script, and the submission checklist.*
