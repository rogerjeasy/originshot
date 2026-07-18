# OriginShot Backend (FastAPI)

FastAPI service orchestrating Genblaze pipelines and Backblaze B2 storage, with Firebase
Auth + Firestore. Designed to **run locally with zero external services** (dev mode) and
flip to managed infra in production.

## Quickstart (local dev — no Firebase/B2/Redis needed)

Requires [Poetry](https://python-poetry.org/) and Python **3.11–3.13** (not 3.14+).

```bash
cd backend
poetry env use 3.12             # pin a supported interpreter (3.11/3.12/3.13)
poetry install                  # core deps + dev tools (pytest, ruff) into ./.venv

cp .env.example .env            # APP_ENV=dev + AUTH_DEV_BYPASS=true by default
poetry run uvicorn app.main:app --reload
```

Open http://localhost:8000/docs (Swagger). In dev mode the API uses an **in-memory store**,
a **fake authenticated user**, local **/media** storage, and a **mock pipeline** (no provider
keys required) so the full upload → generate → verify flow works end-to-end.

## Run the tests

```bash
cd backend
poetry run pytest -q
```

## Generation modes

`GET /healthz` reports the active mode:

- **`mock`** (dev default) — no providers/B2 needed; generated styles reference your upload so the full UX works locally.
- **`genblaze`** — used automatically once **Genblaze is installed, `GMI_API_KEY` is set, and B2 is configured**. Real pipelines (`app/generation.py` → `originshot_pipelines/`) run per style, write to B2 via the Genblaze sink, persist a sidecar manifest, **embed the provenance manifest into the generated media bytes** (`PipelineResult.save` → re-stored content-addressably + re-verified), and record lineage. Each style is isolated, so one provider failure yields a `partial` job rather than a total failure.

  Embedding is controlled by `MANIFEST_EMBED_MODE`: `full` (default — self-contained, standalone `genblaze verify`), `pointer` (privacy — embeds `{hash, manifest_uri}`, full manifest stays in the B2 sidecar), or `none`.

> ✅ **Week-1 SDK lock-in done.** Model IDs, the reference-image kwarg (`image`), and the
> manifest-embedding approach in `originshot_pipelines/` are verified against the installed SDK
> (genblaze 0.4.0 / genblaze-core 0.3.2 / genblaze-gmicloud 0.3.1). `tests/test_sdk_integration.py`
> re-checks every model ID against the live GMI registry so they can't silently drift.

## Going to production

1. `poetry install --extras "firebase worker analytics"` and `poetry run pip install "genblaze[gmicloud,video,parquet]"`.
2. Set real secrets in the environment (see `.env.example`), `AUTH_DEV_BYPASS=false`, and `JOB_QUEUE=arq`.
3. Run the API (`poetry run uvicorn app.main:app`) and the worker (`poetry run arq app.worker.WorkerSettings`) with Redis.
4. Deploy via `infra/Dockerfile.backend` + `infra/render.yaml`.

## Layout

```
app/            FastAPI app: config, auth, firebase, repo, storage, security, worker, api/
originshot_pipelines/   Genblaze pipeline builders (studio, lifestyle, variants, video, provenance)
tests/          pytest suite (health, full flow, security, pipelines)
```

Security model: every route is authenticated and scoped to the caller's `uid`; uploads are
validated + metadata-stripped; per-user quotas guard spend. Full design in
[`../docs/SECURITY.md`](../docs/SECURITY.md).
