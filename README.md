# OriginShot

**One phone photo in. A full marketplace-ready product catalog out — with cryptographic proof of what's real and what's AI.**

OriginShot turns a single product snapshot into studio white-background shots, lifestyle scenes,
on-model images, color/angle variants, and a short product video — every asset stored on
**Backblaze B2** with an embedded, verifiable **Genblaze** provenance manifest that doubles as
AI-disclosure compliance.

> Built for the **Backblaze Generative Media Hackathon**. Generate with Genblaze. Store on Backblaze B2.

| | |
|---|---|
| **Backend** | FastAPI on Render · Genblaze · Backblaze B2 · Firebase Admin |
| **Frontend** | Next.js 15 + React 19 + Tailwind v4 + shadcn/ui on Vercel · Firebase Auth |
| **Generation** | GMI Cloud (primary) + OpenAI / Google / Luma (fallback) |
| **Data** | Firebase Firestore (+ Genblaze ParquetSink analytics) |

## Repository structure

```
originshot/
├── docs/         PROJECT_DESCRIPTION · BUILD_PLAN · SECURITY · DESIGN_SYSTEM
├── backend/      FastAPI app + originshot_pipelines (Genblaze) + tests
├── frontend/     Next.js (App Router) + Tailwind v4 + shadcn/ui
├── infra/        Dockerfile.backend · docker-compose.yml · firestore.rules
└── render.yaml   Render Blueprint (backend) · frontend/vercel.json (Vercel)
```

## Quickstart

**One env file for both apps.** Copy the root template once; the backend (pydantic) and the
frontend (`frontend/next.config.mjs`) both read this single `originshot/.env`:
```bash
cp .env.example .env                               # then fill in your keys
```

**Backend** (runs fully locally — no Firebase/B2/Redis needed in dev):
```bash
cd backend
poetry env use 3.12                                # Python 3.11–3.13 (not 3.14+)
poetry install
poetry run uvicorn app.main:app --reload           # http://localhost:8000/docs
```

**Frontend:**
```bash
cd frontend
npm install
npm run dev                                         # http://localhost:3000
```

The home page is a live **design-system style guide** demonstrating the OriginShot visual
language (see `docs/DESIGN_SYSTEM.md`).

## How it maps to the judging criteria

- **Real-World Utility** — solves the #1 daily, paid-for pain of tens of millions of sellers; provenance addresses emerging AI-disclosure rules.
- **Production Readiness** — Firebase Auth + per-user isolation, multi-provider fallback, async jobs, security headers, rate limits/quotas, live URLs.
- **B2 Storage & Data Orchestration** — content-addressable (deduplicated) asset library on B2 + ParquetSink analytics.
- **Genblaze Usage** — multi-step, chained pipelines (image → variants → video), fallback chains, lineage, and embedded/verifiable provenance manifests.

## Providers & models

Canonical list lives in [`backend/originshot_pipelines/registry.py`](backend/originshot_pipelines/registry.py):
GMI Cloud (Seedream/FLUX/Gemini image; Kling/Seedance video), with OpenAI `gpt-image`,
Google Imagen/Veo, and Luma as fallbacks.

## Security

Authentication on every route, strict per-user data isolation (backend **and** Firestore
rules), server-only secrets, validated uploads, and denial-of-wallet quotas. Full design:
[`docs/SECURITY.md`](docs/SECURITY.md).

## Docs

- [`docs/PROJECT_DESCRIPTION.md`](docs/PROJECT_DESCRIPTION.md) — product, features, market
- [`docs/BUILD_PLAN.md`](docs/BUILD_PLAN.md) — architecture, pipelines, 6-week plan, demo script
- [`docs/SECURITY.md`](docs/SECURITY.md) — threat model + controls (mandatory)
- [`docs/DESIGN_SYSTEM.md`](docs/DESIGN_SYSTEM.md) — the v0 design language

## License

MIT.
