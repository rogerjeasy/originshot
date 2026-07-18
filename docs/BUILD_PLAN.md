# OriginShot — End-to-End Build Plan

> Engineering plan to ship OriginShot for the **Backblaze Generative Media Hackathon** by **August 3, 2026, 5:00 PM EDT**.
> Product context: [`PROJECT_DESCRIPTION.md`](./PROJECT_DESCRIPTION.md).
>
> 🔒 **Security is a first-class, mandatory requirement of this build — not a Week-5 afterthought.** Authentication, per-user data isolation, secret management, upload safety, and denial-of-wallet protection are designed in from Week 1. The complete security & privacy design and threat model live in **[`SECURITY.md`](./SECURITY.md)**, and this plan references it throughout.

This plan is written to be executed by a 1–2 person team in ~6 weeks. Code snippets target the Genblaze SDK API as documented at release; **verify exact model IDs and a few provider kwargs against the installed SDK in Week 1** (flagged inline with ⚠️).

---

## Table of Contents

1. [Guiding Principles](#1-guiding-principles)
2. [Tech Stack](#2-tech-stack)
3. [System Architecture](#3-system-architecture)
4. [Repository Structure](#4-repository-structure)
5. [Prerequisites, Accounts & Env Vars](#5-prerequisites-accounts--env-vars)
6. [Data Model & B2 Layout](#6-data-model--b2-layout)
7. [The Genblaze Pipelines (Core)](#7-the-genblaze-pipelines-core)
8. [Backend API Design](#8-backend-api-design)
9. [Frontend](#9-frontend)
10. [Provenance & Compliance Implementation](#10-provenance--compliance-implementation)
11. [Storage, Dedup & Cost Implementation](#11-storage-dedup--cost-implementation)
12. [Analytics Dashboard](#12-analytics-dashboard)
13. [6-Week Milestone Schedule](#13-6-week-milestone-schedule)
14. [Testing & QA Plan](#14-testing--qa-plan)
15. [Deployment Plan](#15-deployment-plan)
16. [Demo Video Script (3 min)](#16-demo-video-script-3-min)
17. [Submission Checklist](#17-submission-checklist)
18. [Stretch & Post-Hackathon](#18-stretch--post-hackathon)

---

## 1. Guiding Principles

1. **End-to-end path first, polish later.** Get "one photo → one stored, provenance-stamped studio image visible in the UI" working in Week 1. Everything else is breadth on a proven spine.
2. **Make the four judging criteria *visible*, not just present.** Every criterion needs an on-screen moment in the demo (utility, reliability/fallbacks, B2 dedup+analytics, multi-step Genblaze + provenance).
3. **Reliability beats features at judging time.** A live URL that works on the first click (thanks to fallback chains and pre-warmed demo data) outscores a richer app that flakes.
4. **Cut line is sacred.** MVP (§11 of project doc) ships before any stretch work begins.
5. **Provenance is the headliner.** Treat manifests as a first-class product surface, not an implementation detail.
6. **Security is non-negotiable.** Authenticate every request, isolate every user's data, keep all secrets server-side, validate every upload, and cap spend. This is mandatory for both real-world viability and the "Production Readiness" criterion. See [`SECURITY.md`](./SECURITY.md).

---

## 2. Tech Stack

| Layer | Choice | Why |
|---|---|---|
| Orchestration | **Genblaze SDK** (Python 3.11+) | Required; multi-step pipelines, fallback, provenance. |
| Storage | **Backblaze B2** via `S3StorageBackend.for_backblaze` | Required; content-addressable + analytics. |
| Generation | **GMI Cloud** (primary) + OpenAI/Google/Luma (fallback) | Hackathon credits; broad model coverage. |
| Backend | **FastAPI** + **Uvicorn**, deployed on **Render** | Async, embeds Genblaze cleanly, easy deploy on Render. |
| Jobs | **Arq** on **Render Key Value (Redis)**; FastAPI `BackgroundTasks` for the earliest MVP | Generation is long-running; must be async. |
| Database | **Firebase Cloud Firestore** (NoSQL document store) | Stores sellers, SKUs, assets, jobs; real-time listeners give live job status. |
| Data access | **Firebase Admin SDK** (server) + Pydantic for validation | No ORM; Security Rules enforce per-user isolation as defense-in-depth. |
| Auth | **Firebase Authentication** (email/password + OAuth); backend verifies ID tokens via Admin SDK | Managed, secure, MFA-capable. See [`SECURITY.md`](./SECURITY.md). |
| Frontend | **Next.js (React, TypeScript)** + **Tailwind** + **shadcn/ui** | SSR, fast Vercel deploy, polished accessible components, good DX. |
| Deploy | **Vercel** (frontend) + **Render** (backend + worker + Redis) + **Firebase** (Auth/Firestore) | Live URL requirement; managed infra. |
| Analytics read | **DuckDB** over Parquet, or pandas | Reads Genblaze `ParquetSink` output for the dashboard. |
| Security | Firebase Auth · Firestore Rules · scoped B2 presigned URLs · secret mgmt · quotas | **Mandatory** — full design in [`SECURITY.md`](./SECURITY.md). |

> Keep the generation/orchestration logic in a standalone Python package (`originshot_pipelines`) so it's testable and reusable independent of the web layer.

---

## 3. System Architecture

```
                 ┌──────────────────────────────────────────────────────┐
                 │        Frontend (Next.js + Tailwind + shadcn/ui)       │
                 │   Upload · Studio · Gallery · /verify · Analytics      │
                 │   Firebase Auth (client) · Firestore live listeners    │
                 └───────────────┬───────────────────────┬──────────────┘
                                 │ HTTPS + Firebase       │ short-lived
                                 │ ID token (Bearer)      │ presigned B2 URLs
                                 ▼                        │
   ┌──────────────────────────────────────────┐         │
   │      Backend API (FastAPI on Render)      │         │
   │  verify ID token ▶ per-user authz on every │        │
   │  /skus /upload /generate /jobs /verify ... │        │
   └───────┬───────────────────────┬──────────┘         │
           │ enqueue job            │ read/write          │
           ▼                        ▼                     │
   ┌───────────────┐        ┌──────────────────┐         │
   │  Job Worker   │        │   Firestore      │         │
   │ (Arq on Render│        │  sellers / skus /│         │
   │  Key Value)   │        │  assets / jobs   │◀─ rules: owner-only
   │  builds & runs│        └──────────────────┘         │
   │  Genblaze     │                                      │
   └──────┬────────┘                                      │
          │ Pipeline.run(sink=ObjectStorageSink(...))     │
          ▼                                               │
   ┌─────────────────────────────────────────────────────┴───────────┐
   │                          Genblaze SDK                             │
   │  Pipeline → Step(s) → Provider adapters → Manifest (SHA-256)     │
   │  fallback chains · chain=True · abatch_run · from_result lineage  │
   └───────┬───────────────────────────────────────────┬─────────────┘
           │ generation                                 │ persist + embed manifest
           ▼                                            ▼
   ┌──────────────────┐                    ┌──────────────────────────────┐
   │  Providers       │                    │  Backblaze B2 (private bucket) │
   │  GMI Cloud /     │                    │  CONTENT_ADDRESSABLE assets   │
   │  OpenAI / Google │                    │  + embedded manifests         │
   │  / Luma ...      │                    │  + ParquetSink analytics data │
   └──────────────────┘                    └──────────────────────────────┘

   Secrets (provider keys, B2 app key, Firebase service account) live only in
   Render/Vercel secret env — never in the repo, never shipped to the browser.
```

**Request flow (generate):** Frontend sends `POST /skus/{id}/generate` with the user's **Firebase ID token** → API **verifies the token**, confirms the SKU belongs to that `uid`, checks the user's **quota/rate limit**, creates a `job` document in Firestore, and enqueues the worker → worker builds the relevant Genblaze `Pipeline`s, runs them with an `ObjectStorageSink` pointed at B2 → manifests embedded + assets stored content-addressably → worker writes `asset` docs and updates the `job` doc → the frontend **subscribes to the job document via a Firestore real-time listener** (no polling) and renders the pack as assets arrive.

---

## 4. Repository Structure

```
originshot/
├── docs/
│   ├── PROJECT_DESCRIPTION.md
│   └── BUILD_PLAN.md
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI app + routes + security middleware/headers
│   │   ├── api/                 # routers: skus, uploads, generate, jobs, verify, analytics, export
│   │   ├── auth.py             # Firebase ID-token verification dependency (get_current_user)
│   │   ├── firebase.py         # Firebase Admin SDK init (Firestore client)
│   │   ├── repo.py             # Firestore data access (sellers/skus/assets/jobs)
│   │   ├── models.py           # Pydantic schemas (request/response + Firestore doc shapes)
│   │   ├── worker.py           # Arq worker entrypoint
│   │   ├── storage.py          # B2 raw uploads + short-lived presigned URLs
│   │   ├── security.py         # rate limiting, quotas, headers, upload validation
│   │   └── config.py           # settings/env (secrets via env only)
│   ├── originshot_pipelines/     # standalone, testable Genblaze logic
│   │   ├── studio.py
│   │   ├── lifestyle.py
│   │   ├── variants.py
│   │   ├── video.py
│   │   ├── provenance.py
│   │   ├── presets.py          # marketplace specs
│   │   └── registry.py         # provider/model config + pricing
│   ├── tests/
│   ├── pyproject.toml
│   └── .env.example
├── frontend/
│   ├── app/                    # Next.js app router pages
│   ├── components/ui/          # shadcn/ui components
│   ├── lib/firebase.ts         # Firebase client (Auth) init
│   ├── lib/api.ts              # authed fetch wrapper (attaches Firebase ID token)
│   └── package.json
├── infra/
│   ├── Dockerfile.backend
│   ├── docker-compose.yml      # local: api + worker + redis (+ Firebase emulator)
│   ├── render.yaml             # Render: web service + worker + Key Value (Redis)
│   └── firestore.rules         # owner-only Firestore Security Rules (deny by default)
├── SECURITY.md                 # security & privacy design + threat model (mandatory)
└── README.md                   # setup, providers/models, B2+Genblaze + security (submission)
```

---

## 5. Prerequisites, Accounts & Env Vars

**Accounts (most already done per your setup):** Backblaze B2 (bucket + app key), GMI Cloud (credits), plus any fallback provider keys (OpenAI/Google/Luma) you choose.

**Install (Week 1):**
```bash
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install "genblaze[gmicloud,video,all]"          # trim to what you use
pip install fastapi uvicorn firebase-admin arq redis boto3 duckdb python-multipart pillow slowapi
```

**Backend `.env` (secrets — set in Render, never committed):**
```bash
# Backblaze B2 (app key scoped to the single bucket; least privilege)
B2_KEY_ID=...
B2_APP_KEY=...
B2_BUCKET=originshot-media
B2_REGION=us-west-000

# Generation providers
GMI_API_KEY=gmi-...
OPENAI_API_KEY=sk-...          # fallback (optional)
GEMINI_API_KEY=...             # fallback (optional)
LUMAAI_API_KEY=...             # video fallback (optional)
ELEVENLABS_API_KEY=...         # stretch: video SFX

# Firebase Admin (service account) — provide as a Render secret file or JSON env
GOOGLE_APPLICATION_CREDENTIALS=/etc/secrets/firebase-admin.json
FIREBASE_PROJECT_ID=originshot-prod

# App
REDIS_URL=redis://...          # Render Key Value
PUBLIC_BASE_URL=https://originshot-api.onrender.com
ALLOWED_ORIGINS=https://originshot.vercel.app
```

**Frontend `.env.local` (Firebase *web* config is public by design, but still locked down via Auth authorized domains + API-key referrer restrictions):**
```bash
NEXT_PUBLIC_FIREBASE_API_KEY=...
NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN=originshot-prod.firebaseapp.com
NEXT_PUBLIC_FIREBASE_PROJECT_ID=originshot-prod
NEXT_PUBLIC_API_BASE_URL=https://originshot-api.onrender.com
```

> **No generation/provider keys or B2 credentials ever reach the browser.** The frontend holds only the Firebase *web* config and talks to the backend, which holds every real secret. See [`SECURITY.md`](./SECURITY.md) §4.

> **Week 1 spike task:** run a one-file script that generates a single studio image and stores it on B2 with a verifiable manifest. Lock the **exact model IDs** and the **reference-image kwarg** (see ⚠️ in §7) before building anything else.

---

## 6. Data Model & B2 Layout

**Firestore data model (NoSQL document collections):**

```
sellers/{uid}                       # mirrors the Firebase Auth user; profile + brand_kit + usage counters
  ├── skus/{skuId}                  # product: title, category, description, originalSha256
  │     └── assets/{assetId}        # generated/original media (shape below)
  └── jobs/{jobId}                  # generation job status (the real-time listener target)
```

Every document is **owned by and scoped to a single `uid`** (the authenticated user). The backend always derives `uid` from the *verified* Firebase ID token — never from client input — and Firestore Security Rules enforce owner-only access as defense-in-depth.

**Asset document shape (validated with Pydantic on the server):**
```python
class AssetDoc(BaseModel):
    id: str
    sku_id: str
    owner_uid: str                   # set server-side from the verified token
    sha256: str                      # content address (B2 key derives from this)
    b2_key: str                      # object key; URLs are short-lived presigned, never stored public
    modality: str                    # image | video
    style: str                       # original | studio | lifestyle | onmodel | variant | video
    is_authentic: bool = False       # True only for the uploaded original
    parent_sha256: str | None        # lineage to the authentic source
    run_id: str | None
    provider: str | None; model: str | None
    manifest_key: str | None         # sidecar manifest object in B2
    mime_type: str | None; width: int | None; height: int | None; duration: float | None
    created_at: datetime
```

**Firestore Security Rules (owner-only, deny by default — `infra/firestore.rules`):**
```
rules_version = '2';
service cloud.firestore {
  match /databases/{db}/documents {
    match /sellers/{uid} {
      allow read: if request.auth != null && request.auth.uid == uid;
      allow write: if false;          // all writes go through the backend (Admin SDK)
      match /{document=**} {
        allow read: if request.auth != null && request.auth.uid == uid;
        allow write: if false;        // clients never write directly
      }
    }
  }
}
```
> Clients may *read* their own data directly (this powers real-time job listeners), but **all writes flow through the backend**, which validates input, enforces quotas, and sets `owner_uid` from the verified token. The Admin SDK bypasses these rules, so the server remains the only writer. Full rationale in [`SECURITY.md`](./SECURITY.md) §3.

**B2 bucket layout** (Genblaze manages asset keys via `KeyStrategy`; we add logical sidecars):

```
originshot-media/
├── assets/<sha[:2]>/<sha[2:4]>/<sha>.<ext>     # CONTENT_ADDRESSABLE (dedup) — generated + originals
├── manifests/<run_id>/<step>.json              # sidecar provenance (also embedded in files)
├── exports/<sku_id>/<marketplace>.zip          # generated export packs
└── data/                                        # ParquetSink analytics
```

> Originals and generated assets both go to the content-addressable `assets/` space, so re-uploading the same photo or regenerating an identical output never double-stores — the dedup cost story made literal.

---

## 7. The Genblaze Pipelines (Core)

All pipeline builders live in `originshot_pipelines/` and return Genblaze `Pipeline` objects so they're unit-testable with mocked providers.

> ✅ **Week-1 verified — the code snippets below are illustrative; `originshot_pipelines/registry.py` is the source of truth.** Confirmed against genblaze 0.4.0 / genblaze-core 0.3.2 / genblaze-gmicloud 0.3.1:
> - **GMI Cloud image models are edit/i2i only** (no `gemini-2.5-flash-image`/`flux-kontext`/`seedream`). Real IDs: `seededit-3-0-i2i-250628`, `reve-edit-20250915`, `reve-edit-fast-20251030`, `reve-remix-*`, `bria-genfill`, `bria-eraser`. This *fits* our use-case (edit a real photo → studio/lifestyle/variant). A true text→image→video chain would need a text→image provider (e.g. Google Imagen).
> - **Video IDs are real**: `Kling-Image2Video-V2.1-Master` (primary), fallbacks `pixverse-v5.6-i2v`, `wan2.6-r2v`; also `Kling-Text2Video-V2.1-Master`, `Veo3`/`Veo3-Fast`. (`seedance-*` / `luma-dream-machine` are **not** GMI models; Luma is a separate provider package, not a GMI `fallback_models` entry.)
> - **Reference-image kwarg = `image`** (both image & video `param_allowlist`s accept `image`/`image_url`); `aspect_ratio` and video `duration` are allow-listed. Provider classes `GMICloudImageProvider` / `GMICloudVideoProvider` import from `genblaze_gmicloud` ✓.
> - **Result shapes**: `provider`/`model`/`cost_usd` live on the **Step**, not the Asset; `Asset` uses `media_type` (not `mime_type`) and has no storage `key`; `Manifest` exposes `canonical_hash`, `manifest_uri`, `to_canonical_json()`, `verify()`.
> - **`Pipeline.arun(sink=…, timeout=…)`** is correct; `step(provider, *, model, prompt, modality, fallback_models, **params)` — the source image, `aspect_ratio`, `duration` all pass through `**params`.

### 7.0 Shared storage sink

```python
# originshot_pipelines/storage.py
import os
from genblaze_core import ObjectStorageSink, KeyStrategy, ParquetSink
from genblaze_s3 import S3StorageBackend

def make_sink() -> ObjectStorageSink:
    return ObjectStorageSink(
        S3StorageBackend.for_backblaze(os.environ["B2_BUCKET"]),
        key_strategy=KeyStrategy.CONTENT_ADDRESSABLE,   # dedup → cost story
        parquet_sink=ParquetSink("data/"),              # analytics export
        # embed_policy=EmbedPolicy(redact_prompts=False),  # ⚠️ confirm: auto-embed manifests in files
    )
```

### 7.1 Studio shot (image edit, with fallback)

```python
# originshot_pipelines/studio.py
from genblaze_core import Pipeline, Modality
from genblaze_gmicloud import GMICloudImageProvider

def build_studio_pipeline(source_image_uri: str, product_desc: str) -> Pipeline:
    return (
        Pipeline("originshot-studio")
        .step(
            GMICloudImageProvider(),
            model="gemini-2.5-flash-image",          # ⚠️ confirm image-edit model id
            prompt=(
                f"Professional e-commerce product photograph of {product_desc}. "
                "Pure white seamless background (#FFFFFF), soft even studio lighting, "
                "centered, sharp focus, true-to-life color, no props, no text."
            ),
            modality=Modality.IMAGE,
            image=source_image_uri,                  # ⚠️ confirm reference-image kwarg name
            aspect_ratio="1:1",
            fallback_models=["flux-kontext", "gpt-image-1"],   # provider/model resilience
        )
    )
```

### 7.2 Lifestyle scenes (parallel fan-out)

```python
# originshot_pipelines/lifestyle.py
import asyncio
from genblaze_core import Pipeline, Modality
from genblaze_gmicloud import GMICloudImageProvider

SCENES = [
    "on a sunlit wooden kitchen counter, soft morning light",
    "on a modern marble bathroom shelf, spa atmosphere",
    "on a minimalist office desk beside a laptop, clean and bright",
    "outdoors on a rustic café table, shallow depth of field",
]

def _scene_pipeline(source_image_uri: str, product_desc: str, scene: str) -> Pipeline:
    return Pipeline("originshot-lifestyle").step(
        GMICloudImageProvider(),
        model="gemini-2.5-flash-image",   # ⚠️
        prompt=f"{product_desc} placed {scene}, realistic shadows and reflections, lifestyle product photography",
        modality=Modality.IMAGE,
        image=source_image_uri,           # ⚠️
        aspect_ratio="4:5",
        fallback_models=["flux-kontext", "gpt-image-1"],
    )

async def run_lifestyle(source_image_uri, product_desc, sink, scenes=SCENES):
    pipes = [_scene_pipeline(source_image_uri, product_desc, s) for s in scenes]
    return await asyncio.gather(*[p.arun(sink=sink, timeout=300) for p in pipes])
```

> For *same-prompt* variation (e.g., several takes of one scene), use `pipeline.abatch_run(sink=sink, count=4)` instead of N pipelines.

### 7.3 Variant fan-out (color / angle)

```python
# originshot_pipelines/variants.py
def build_variant_prompts(product_desc, colors=(), angles=()):
    base = "studio product photo on pure white background, soft lighting"
    out = []
    for c in colors:
        out.append(f"{product_desc} in {c} color, {base}")
    for a in angles:
        out.append(f"{product_desc}, {a} view, {base}")
    return out
# build one image pipeline per prompt, run with asyncio.gather (see 7.2 pattern)
```

### 7.4 Hero product video (image-to-video)

The hero studio image is already generated and provenance-anchored; feed it into a video step. (Use `chain=True` if you want text→image→video in one pass instead.)

```python
# originshot_pipelines/video.py
from genblaze_core import Pipeline, Modality
from genblaze_gmicloud import GMICloudVideoProvider

def build_hero_video(hero_image_uri: str, product_desc: str) -> Pipeline:
    return Pipeline("originshot-hero-video").step(
        GMICloudVideoProvider(),
        model="Kling-Image2Video-V2.1-Master",   # ⚠️ confirm id
        prompt="slow turntable rotation with a gentle camera push-in, premium product reveal, clean background",
        modality=Modality.VIDEO,
        image=hero_image_uri,                     # ⚠️ image-to-video input kwarg
        duration=5,
        aspect_ratio="1:1",
        fallback_models=["seedance-2-0-260128", "luma-dream-machine"],
    )

# Single-pass alternative (text → image → video) using chaining + lineage:
def build_chained_video(product_desc: str) -> Pipeline:
    from genblaze_gmicloud import GMICloudImageProvider
    return (
        Pipeline("originshot-chained-video", chain=True)
        .step(GMICloudImageProvider(), model="seedream-5.0-lite",
              prompt=f"{product_desc}, studio product photo, white background",
              modality=Modality.IMAGE)
        .step(GMICloudVideoProvider(), model="Kling-Image2Video-V2.1-Master",
              prompt="slow turntable, subtle push-in", modality=Modality.VIDEO, duration=5)
    )
```

### 7.5 Running a full job (worker side)

```python
# backend/app/worker.py (sketch)
from originshot_pipelines.storage import make_sink
from originshot_pipelines.studio import build_studio_pipeline
from originshot_pipelines.lifestyle import run_lifestyle
from originshot_pipelines.video import build_hero_video
from originshot_pipelines.provenance import record_asset

async def run_generation(job_id, sku, source_uri, styles):
    sink = make_sink()
    results = {}

    # 1) Studio (also becomes the hero image for video)
    studio = await build_studio_pipeline(source_uri, sku.description).arun(sink=sink, timeout=300)
    hero = studio.run.steps[0].assets[0]
    await record_asset(sku, hero, style="studio", parent_sha256=sku.original_sha256, run=studio)

    # 2) Lifestyle (parallel)
    if "lifestyle" in styles:
        for res in await run_lifestyle(source_uri, sku.description, sink):
            await record_asset(sku, res.run.steps[0].assets[0], "lifestyle", sku.original_sha256, res)

    # 3) Hero video (from the studio hero image)
    if "video" in styles:
        vid = await build_hero_video(hero.url, sku.description).arun(sink=sink, timeout=600)
        await record_asset(sku, vid.run.steps[0].assets[0], "video", hero.sha256, vid)

    return results
```

### 7.6 Asset extraction (what we persist)

```python
asset = result.run.steps[0].assets[0]
# asset.url (durable B2), asset.sha256, asset.mime_type, asset.duration
# result.manifest.canonical_hash, result.manifest.verify()
```

---

## 8. Backend API Design

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/skus` | Create a product (title, category, description). |
| `POST` | `/skus/{id}/upload` | Upload original photo(s); hashes, stores on B2 as authentic, returns asset. |
| `POST` | `/skus/{id}/generate` | Body: `{styles: [...], marketplaces: [...]}`. Creates `Job`, enqueues worker, returns `run_id`. |
| `GET` | `/jobs/{run_id}` | Poll status + produced assets. |
| `GET` | `/skus/{id}/assets` | List all assets for a product. |
| `GET` | `/verify/{sha256}` | **Public.** Returns integrity (verify result), authentic/AI flag, and **non-sensitive** lineage; prompts/params redacted via `EmbedPolicy`. |
| `POST` | `/verify` | **Public.** Upload a file → re-extract its embedded manifest, re-run `verify()` from the bytes, and return integrity + (if matched) lineage. |
| `GET` | `/assets/{sha256}/manifest` | Raw manifest JSON. |
| `GET` | `/analytics` | Dashboard metrics from Parquet (assets, storage, dedup savings, cost, provider mix). |
| `POST` | `/skus/{id}/export` | Build per-marketplace ZIP (images + video + `disclosure.txt` + manifests). |

**Notes**
- **Every endpoint except `/verify/*` and `/healthz` requires a valid Firebase ID token** (`Authorization: Bearer <token>`), verified server-side via the Admin SDK. The user's `uid` comes from the token and scopes all reads/writes — client-supplied IDs are never trusted (IDOR prevention). See [`SECURITY.md`](./SECURITY.md) §2–§3.
- Enforce **per-user generation quotas and rate limits** *before* enqueuing a job (denial-of-wallet protection).
- **Validate uploads** (magic-byte type check, size/dimension caps, EXIF/GPS strip) before storing or processing.
- `generate` must be **async** (Arq job) — never block the request on generation.
- Return **short-lived presigned** B2 URLs for private assets; the bucket is never public. The `/verify` page returns only non-sensitive data.
- Standardize errors and surface partial success (`status: "partial"` when some styles failed but fallbacks exhausted).

---

## 9. Frontend

Built with **Next.js (App Router) + Tailwind + shadcn/ui**. Auth is **Firebase Authentication** (client SDK); the `lib/api.ts` fetch wrapper attaches the user's ID token to every backend call, and protected pages redirect unauthenticated users to sign-in. Live data uses **Firestore real-time listeners** rather than polling.

**Pages (Next.js app router):**
1. **Landing** — value prop + "Try with one photo" CTA.
2. **Upload / New SKU** — drag-drop, product details, style + marketplace selectors, "Generate everything" button.
3. **Job progress** — live status per style with skeleton tiles via a **Firestore real-time listener** on the job doc (no polling).
4. **SKU gallery** — grid of outputs; each tile shows an **"AI-generated"** or **"Authentic"** badge, download, and "Verify" link.
5. **/verify** (public) — drop a file or paste a SHA → integrity result, provider/model/prompt, lineage to original.
6. **Analytics dashboard** — assets generated, storage used, **dedup savings**, est. cost/SKU, provider mix, fallback rate.
7. **Settings / Brand Kit** (stretch).

**UX principles:** the magic is "one input → many outputs," so make the before→after and the badge/verify moment obvious and screenshot-worthy for the demo.

---

## 10. Provenance & Compliance Implementation

```python
# originshot_pipelines/provenance.py
from pathlib import Path
from genblaze_core.media import Mp4Handler   # ⚠️ image handlers: PngHandler/WebpHandler/JpegHandler (confirm names)

def embed_and_verify(local_path: Path, manifest):
    handler = Mp4Handler() if local_path.suffix == ".mp4" else _image_handler(local_path)
    handler.embed(local_path, manifest)
    extracted = handler.extract(local_path)
    assert extracted.verify(), "manifest verification failed"
    return extracted

def disclosure_text(asset) -> str:
    if asset.is_authentic:
        return "Authentic photo — unedited original. Verifiable via OriginShot manifest."
    return (f"AI-generated image. Model: {asset.model} ({asset.provider}). "
            f"Derived from authentic source {asset.parent_sha256[:12]}. "
            f"Provenance verifiable via OriginShot (SHA-256 manifest embedded).")
```

**Implementation tasks:**
- [x] ~~Prefer automatic embedding via `EmbedPolicy` on the sink~~ — **resolved Week 1: embedding is explicit.** The generation flow embeds via `PipelineResult.save(path, embed=True, policy=EmbedPolicy(...))` (`app/generation.py::_embed_and_store` → `originshot_pipelines/provenance.py`), then re-stores the embedded bytes content-addressably and re-extracts to verify. Mode is configurable (`MANIFEST_EMBED_MODE` = `full`/`pointer`/`none`); `full` keeps the file standalone-verifiable, `pointer` redacts prompts and points to the B2 sidecar.
- [x] Persist a **sidecar manifest** to B2 and store `manifest_key` on the `Asset` (the `embedded` flag records whether the bytes carry the manifest).
- `/verify` endpoints: **`GET /verify/{sha}`** returns integrity + lineage from the record; **`POST /verify`** (file upload) **re-extracts the embedded manifest from the actual bytes, re-runs `verify()`, and checks content-binding** — never trusts stored state — then matches the bytes' SHA-256 to a record for lineage. A downloaded `full`-mode asset self-verifies even with no DB record. Both surface the `embedded` flag; the upload route also returns `content_bound`.
- **Content-binding (tamper-evidence).** `verify()` only proves the manifest's *internal* integrity, and the SDK exposes no content-binding API — but the manifest's canonical hash commits to each asset's `sha256`. So `POST /verify` recomputes the file's **canonical content hash** (strips the embedded genblaze manifest, re-hashes — `provenance.canonical_content_hash`) and compares it to the signed hash → `content_bound = True/False`. Covered for **PNG** (iTXt), **MP4** (uuid box, ISO-BMFF walk), **JPEG** (APP1 XMP), and **WebP** (`XMP ` RIFF chunk). A byte-exact match to a stored asset also counts as bound. `content_bound=False` ⇒ a valid manifest embedded into altered pixels/frames — surfaced as a **"Tampered"** disclosure.
- **Why JPEG/WebP need a byte-preserving embed.** PNG/MP4 embeds are clean metadata appends, so stripping recovers the exact committed bytes. The SDK's JPEG/WebP handlers **re-encode through Pillow** (the original bytes are lost), which would make a strip-and-rehash check impossible — and a naïve one would false-flag every legitimate file as tampered. So `provenance.embed_manifest` injects the manifest **byte-preservingly** for JPEG (APP1 XMP segment after SOI) and WebP (appended `XMP ` chunk + fixed RIFF size) in `full` mode, leaving the original bytes intact while staying extractable by the SDK. `pointer`/`none` modes and other formats fall back to the byte-exact stored-record match (`content_bound=None` if undetermined).
- Export packs include a human-readable `disclosure.txt` and the sidecar manifests.
- **Demo beat:** run the CLI live — `genblaze verify <downloaded>.mp4` and `genblaze extract <downloaded>.png`.

---

## 11. Storage, Dedup & Cost Implementation

- Use `KeyStrategy.CONTENT_ADDRESSABLE` so identical bytes (re-uploaded originals, shared scene plates, identical regenerations) store once.
- Track **logical vs. physical** bytes in the DB: sum of asset sizes referenced vs. unique objects stored → render **dedup savings** in the dashboard.
- Lean on B2's low storage + favorable egress economics; show estimated monthly cost for a 1,000-SKU catalog vs. an S3 baseline as a slide in the demo.
- Cache aggressively in dev to avoid burning generation credits: content addressing means re-running the same prompt+input is effectively free to store.

---

## 12. Analytics Dashboard

Genblaze's `ParquetSink` writes run/asset metadata to `data/`. Read it for the dashboard:

```python
import duckdb
con = duckdb.connect()
df = con.execute("""
    SELECT provider, model, modality,
           COUNT(*) AS assets,
           SUM(size_bytes) AS logical_bytes,
           COUNT(DISTINCT sha256) AS unique_objects
    FROM read_parquet('data/**/*.parquet')
    GROUP BY 1,2,3
""").df()
```

Surface: total assets, unique objects, **dedup savings %**, estimated cost (via `ModelRegistry` pricing), provider/model mix, and **fallback rate** (how often the primary model failed and a fallback succeeded — a direct "production readiness" proof point).

---

## 13. 6-Week Milestone Schedule

> Today: **2026-06-23**. Submission: **2026-08-03, 5:00 PM EDT**. Six working weeks. End each week with something demoable.

### Week 1 — Jun 23–29 · Spike & Skeleton  ⏱️ *De-risk the SDK*
- [x] Install Genblaze (0.4.0 / core 0.3.2 / gmicloud 0.3.1); pipeline runs and manifest `verify()` passes (proven via `MockProvider`; real B2 run pending live keys).
- [x] **Locked exact model IDs** and the **reference-image kwarg** (`image`) — see `originshot_pipelines/registry.py` + `tests/test_sdk_integration.py`. (Findings below.)
- [x] Confirmed manifest embedding is **manual/explicit** — `ObjectStorageSink` has no `embed_policy`; embed via `PipelineResult.save(path, embed=True, policy=EmbedPolicy(...))` / `SmartEmbedder`.
- [ ] Scaffold repo: FastAPI hello-world, Next.js (Tailwind + shadcn/ui) hello-world, docker-compose, `.env`.
- [ ] **Firebase project**: enable Auth + Firestore; wire Firebase Admin into the backend; implement the ID-token verification dependency; deploy **deny-by-default Firestore rules**.
- [ ] Firestore data model + B2 bucket layout (private, least-privilege key) created.
- **Exit criteria:** `python spike.py photo.jpg` produces a verifiable studio PNG on B2.

### Week 2 — Jun 30–Jul 6 · Core Generation End-to-End
- [ ] `originshot_pipelines`: studio + lifestyle + variant fan-out builders (unit-tested with mocks).
- [ ] `POST /skus`, `/upload` (hash + authentic anchor), `/generate` (Arq job), `/jobs/{id}` — **all authenticated and scoped to the caller's `uid`** (no cross-user access).
- [ ] Worker runs studio + lifestyle and writes `Asset` rows.
- [ ] Frontend: upload → generate → gallery grid renders real outputs.
- **Exit criteria:** one photo → multiple stored images visible in the UI via the deployed-ish stack.

### Week 3 — Jul 7–13 · Video + Provenance (the headliner)
- [ ] Image-to-video pipeline + worker step; async progress UI.
- [ ] Manifest embed/verify wired; sidecar manifests on B2; `manifest_url` persisted.
- [ ] Public `/verify` page + `/verify/{sha}` endpoint; authentic/AI badges across gallery.
- [ ] Fallback chains verified by forcing a primary-model failure.
- **Exit criteria:** download a generated file, run `genblaze verify`, see lineage in `/verify`.

### Week 4 — Jul 14–20 · Presets, Analytics, Export
- [ ] Marketplace presets (Amazon/Etsy/Shopify/eBay/Social) sizing + rules.
- [ ] Analytics dashboard from ParquetSink (assets, dedup savings, cost, provider mix, fallback rate).
- [ ] Export packs (ZIP + `disclosure.txt` + manifests).
- [ ] Basic brand kit (colors/style reused in prompts).
- **Exit criteria:** full MVP feature set works locally end-to-end.

### Week 5 — Jul 21–27 · Security Hardening & Live Deploy
- [ ] **Work through the entire [`SECURITY.md`](./SECURITY.md) checklist — mandatory, not optional.**
- [ ] Rate limits + per-user generation quotas (denial-of-wallet), security headers (CSP/HSTS), CORS allowlist, request size limits.
- [ ] Upload hardening: magic-byte type checks, size/dimension caps, EXIF/GPS stripping, decompression-bomb guards; **content moderation on inputs and outputs**.
- [ ] Secrets only in Render/Vercel secret env; **least-privilege B2 app key**; short-TTL presigned URLs; dependency scan (`pip-audit`, `npm audit`); secret scan (`gitleaks`).
- [ ] Robust error/partial-success handling, retries/timeouts tuned.
- [ ] Deploy: frontend → **Vercel**, backend + worker → **Render** (+ Key Value/Redis), Auth/DB → **Firebase** (rules deployed).
- [ ] Smoke test on the **live URL**; pre-warm a polished demo SKU and cache its outputs.
- [ ] Start stretch (on-model / SFX) only if everything above is green.
- **Exit criteria:** public URL works reliably on a cold first click **and passes the security checklist**.

### Week 6 — Jul 28–Aug 3 · Freeze, Demo, Submit
- [ ] **Feature freeze Jul 29.** Only bug fixes after.
- [ ] Write `README.md` (setup, providers/models list, B2 + Genblaze integration + security summary).
- [ ] Final **security pass**: Firestore rules deployed, every route token-verified, no secrets in repo (`gitleaks` clean), HTTPS-only, presigned-URL TTLs short, keys rotated post-demo.
- [ ] Record + edit the **3-min demo video** (script in §16).
- [ ] Dry-run the full Devpost submission; verify every required field.
- [ ] **Submit by Aug 3, 2:00 PM EDT** (3-hour buffer before the 5 PM cutoff).
- **Exit criteria:** submitted, live URL + repo + video all verified by a second person.

---

## 14. Testing & QA Plan

- **Unit:** pipeline builders return correct steps/models/prompts (mock providers); preset sizing math; disclosure text.
- **Integration:** one real low-cost generation per modality; manifest `verify()` returns true; `/verify` round-trips a downloaded file.
- **Dedup test:** upload the same photo twice and regenerate identical output → exactly one B2 object; dashboard shows savings.
- **Resilience test:** force primary model error → confirm fallback succeeds and `Job` still completes.
- **End-to-end smoke (scripted):** create SKU → upload → generate all → poll → export, asserting asset counts.
- **Judge dry-run:** a fresh person uses the live URL cold and follows the demo path; fix any first-click failure.
- **Browser check:** Chrome + Safari + mobile width (sellers are often mobile).
- **Security tests:** unauthenticated requests are rejected (401); user A cannot read or write user B's SKUs/assets/jobs (IDOR); oversized/non-image uploads rejected; quota/rate-limit enforced; Firestore rules unit-tested against the emulator; `gitleaks`/`pip-audit`/`npm audit` clean. (Mirrors the [`SECURITY.md`](./SECURITY.md) checklist.)

---

## 15. Deployment Plan

- **Frontend → Vercel:** auto-deploy from `frontend/`; set `NEXT_PUBLIC_*` Firebase web config + `NEXT_PUBLIC_API_BASE_URL`. Restrict the Firebase web API key (HTTP referrers) and add the Vercel domain to Firebase Auth authorized domains.
- **Backend + worker → Render:** `infra/Dockerfile.backend` as a **web service** + a **background worker** (`render.yaml`), plus **Render Key Value (Redis)** for Arq. The Firebase Admin service account is provided as a Render **secret file** (`/etc/secrets/firebase-admin.json`).
- **Auth + DB → Firebase:** Firebase Authentication + Cloud Firestore; deploy `infra/firestore.rules` (owner-only, deny by default).
- **Storage → Backblaze B2:** **private** bucket; **least-privilege app key** scoped to the one bucket; CORS limited to the app origin; access only via **short-lived presigned URLs**.
- **Secrets:** only in Render/Vercel secret env (and the Render secret file for the Firebase key); never in the repo. Rotate before and after the public demo.
- **Observability:** Genblaze `LoggingTracer` (or OTel) on; structured logs **with no secrets/PII**; `/healthz` endpoint; alert on cost/error spikes.
- **Cost guardrails:** cap resolution/duration in prod defaults; per-user generation quota + concurrency caps.

> Full hardening steps and the threat model live in [`SECURITY.md`](./SECURITY.md).

---

## 16. Demo Video Script (3 min)

| Time | Beat | On screen |
|---|---|---|
| 0:00–0:20 | **The pain.** "Every seller's worst chore: product photos." | A bad, dim phone photo of a product. |
| 0:20–1:20 | **The magic.** Upload that one photo → click "Generate everything." | Studio, lifestyle, variants, and a 5-sec video populate the gallery. |
| 1:20–2:00 | **Provenance (the differentiator).** Download a file; run `genblaze verify`; open `/verify`. | Terminal shows verified ✓; UI shows authentic vs. AI lineage + auto disclosure. |
| 2:00–2:35 | **B2 + data orchestration.** Open the analytics dashboard. | Content-addressable library, **dedup savings**, cost/SKU, provider mix, fallback rate. |
| 2:35–3:00 | **Why it wins.** Per-marketplace export + one-line on the business. | Export ZIP downloading; closing value-prop card. |

> Pre-generate the demo SKU's heavy assets (especially video) so playback is instant. Narrate the four judging criteria implicitly through the beats.

---

## 17. Submission Checklist

Mapped to the hackathon's required submission materials:

- [ ] **Functional app at a public URL** (verified cold, second device).
- [ ] **GitHub repo** with clear setup instructions (`README.md`).
- [ ] **List of AI providers & models used** (keep `originshot_pipelines/registry.py` as the source of truth; mirror in README).
- [ ] **Explanation of B2 integration** (content-addressable sink, manifests, Parquet analytics).
- [ ] **Explanation of Genblaze integration** (multi-step pipelines, fallback, chaining, lineage, provenance embed/verify/replay).
- [ ] **~3-minute demo video** (≤ 3:00).
- [ ] Devpost project page filled (title, tagline, screenshots, tech list).
- [ ] **Security**: Firestore rules deployed, all routes auth-checked, secrets only in env (secret scan clean), HTTPS-only, scoped B2 keys — summarized in `README.md`, detailed in [`SECURITY.md`](./SECURITY.md).
- [ ] License + `.env.example` + no secrets committed.

---

## 18. Stretch & Post-Hackathon

- On-model shots (apparel/accessories) with diversity options.
- Infographic / feature-callout overlays.
- AgentLoop brand-consistency refinement; saved brand kits.
- Video SFX/music (ElevenLabs / Stability Audio) muxed in.
- Direct publishing to Shopify/Etsy APIs.
- Team seats, run history, **one-click `genblaze replay`** to regenerate any past asset in a new size/style.
- API / white-label for marketplaces and PIM platforms.

---

*Build the spine in Week 1, make every judging criterion a visible moment, and let provenance be the thing they remember.*
