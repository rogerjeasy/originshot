# OriginShot — Security & Privacy Design

> **Security is a mandatory, first-class requirement of OriginShot — designed in from day one, not bolted on.**
> This document defines the threat model, the controls, and the pre-launch checklist. It is referenced throughout [`BUILD_PLAN.md`](./BUILD_PLAN.md) and summarized in the product's [`PROJECT_DESCRIPTION.md`](./PROJECT_DESCRIPTION.md).

- **Stack in scope:** Firebase Authentication + Cloud Firestore · FastAPI on Render (+ Arq worker + Redis) · Next.js (Tailwind + shadcn/ui) on Vercel · Backblaze B2 · Genblaze SDK · generation providers (GMI Cloud, OpenAI, Google, Luma, …).
- **Last updated:** 2026-06-24
- **Owner:** OriginShot team

**Why this matters for the hackathon.** The judging rubric weights **Production Readiness** heavily. A generative app that handles user accounts, user-uploaded media, paid third-party APIs, and durable cloud storage is *only* production-ready if it is secure. This document is how OriginShot demonstrates that.

---

## Table of Contents

1. [Security Principles](#1-security-principles)
2. [Threat Model](#2-threat-model)
3. [Authentication (Firebase Auth)](#3-authentication-firebase-auth)
4. [Authorization & Data Isolation](#4-authorization--data-isolation)
5. [Secrets & Key Management](#5-secrets--key-management)
6. [Input Validation & Upload Security](#6-input-validation--upload-security)
7. [Content Safety & Moderation](#7-content-safety--moderation)
8. [Storage Security (Backblaze B2)](#8-storage-security-backblaze-b2)
9. [API Security](#9-api-security)
10. [Abuse & Denial-of-Wallet Controls](#10-abuse--denial-of-wallet-controls)
11. [Provenance & Integrity Security](#11-provenance--integrity-security)
12. [Privacy & Compliance](#12-privacy--compliance)
13. [Dependency & Supply-Chain Security](#13-dependency--supply-chain-security)
14. [Infrastructure & Deployment Security](#14-infrastructure--deployment-security)
15. [Logging, Monitoring & Incident Response](#15-logging-monitoring--incident-response)
16. [Secure SDLC](#16-secure-sdlc)
17. [Pre-Launch Security Checklist](#17-pre-launch-security-checklist)
18. [Threat → Control Summary](#18-threat--control-summary)
19. [Responsible Disclosure](#19-responsible-disclosure)

---

## 1. Security Principles

1. **Zero trust in the client.** Every request is authenticated and authorized server-side. The browser is treated as hostile; nothing it sends (IDs, flags, prices, role claims) is trusted without verification.
2. **Least privilege everywhere.** Each credential (B2 app key, Firebase service account, provider keys) has the minimum scope needed and nothing more.
3. **Defense in depth.** Multiple independent layers (backend authz **and** Firestore rules; CORS **and** auth; quotas **and** billing alerts) so one failure isn't catastrophic.
4. **Secrets stay server-side.** Provider and storage credentials never reach the browser, the repo, logs, or the provenance manifest.
5. **Secure by default.** Deny-by-default rules, private buckets, short-lived URLs, validated inputs. Opening access is a deliberate, reviewed act.
6. **Fail closed.** On auth/validation/quota errors, deny the action — never degrade to "allow."
7. **Privacy by design.** Collect the minimum, strip what we don't need (EXIF/GPS), and give users control (export/delete).
8. **Auditable.** Security-relevant events are logged (without secrets/PII) so abuse and incidents are detectable.

---

## 2. Threat Model

### 2.1 Assets to protect
| Asset | Why it matters |
|---|---|
| User accounts & PII (email, profile) | Account takeover, privacy breach. |
| User-uploaded product photos | May contain private/competitive info; integrity matters for provenance. |
| Generated media library | The user's paid output; tampering breaks trust. |
| Provider API keys (GMI/OpenAI/…) | Theft = direct financial loss + abuse under our identity. |
| Backblaze B2 credentials | Theft = data exfiltration/destruction. |
| Firebase service account | Theft = full database compromise. |
| Provenance manifests | Their integrity *is* the product's trust promise. |
| Billing / generation credits | Abuse = denial-of-wallet, financial loss. |

### 2.2 Threat actors
- **External attacker** — probing the API, hunting for IDOR/auth bypass, credential leaks, injection.
- **Malicious authenticated user** — abusing generation for cost/abuse, attempting to access other users' data, uploading disallowed content.
- **Curious/accidental user** — IDOR via guessable IDs, oversharing.
- **Supply-chain attacker** — compromised dependency or provider SDK.
- **Insider / operator error** — leaked secret, misconfigured bucket, secret in logs.

### 2.3 STRIDE overview
| Threat | Example against OriginShot | Primary control(s) |
|---|---|---|
| **S**poofing | Forged identity / stolen token | Firebase ID-token verification (§3) |
| **T**ampering | Altering another user's asset; forging "authentic" badge | Authz + Firestore rules (§4); manifest integrity (§11) |
| **R**epudiation | "I didn't generate that" | Audit logs (§15); provenance lineage (§11) |
| **I**nformation disclosure | Reading others' media; secret leak; prompt leak in public manifest | Data isolation (§4); secret mgmt (§5); EmbedPolicy redaction (§11) |
| **D**enial of service / **wallet** | Flooding generation to burn credits/cost | Rate limits + quotas + concurrency caps (§10) |
| **E**levation of privilege | Normal user acting as another/admin | Server-derived `uid`; deny-by-default rules (§4) |

### 2.4 Top risks (ranked) and where they're addressed
1. **IDOR / broken access control** → §4
2. **Denial-of-wallet via generation abuse** → §10
3. **Secret leakage** (repo, client, logs) → §5, §15
4. **Malicious/unsafe uploads & generated content** → §6, §7
5. **Public/over-permissive storage** → §8

---

## 3. Authentication (Firebase Auth)

**Identity provider:** Firebase Authentication (email/password + OAuth providers such as Google). Email verification required; optional MFA (TOTP) for accounts that want it.

**Rule: the backend independently verifies every Firebase ID token.** The client obtains an ID token from Firebase and sends it as `Authorization: Bearer <token>`. The FastAPI backend verifies it with the Admin SDK on **every** protected request and derives `uid` from the verified token.

```python
# app/auth.py  (illustrative — not part of "the build" yet)
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from firebase_admin import auth as fb_auth

bearer = HTTPBearer(auto_error=True)

async def get_current_user(cred: HTTPAuthorizationCredentials = Depends(bearer)) -> dict:
    try:
        # check_revoked=True rejects disabled/revoked sessions; verifies signature, exp, aud, iss
        decoded = fb_auth.verify_id_token(cred.credentials, check_revoked=True)
    except Exception:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired token")
    if not decoded.get("email_verified", False):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Email not verified")
    return decoded  # contains the trusted `uid`
```

**Controls**
- Verify signature, expiry, audience, and issuer (handled by `verify_id_token`); set `check_revoked=True`.
- Require `email_verified` for any data-mutating action.
- Tokens are short-lived (≈1h) and auto-refreshed client-side; never stored in `localStorage` if avoidable — prefer in-memory + Firebase's secure persistence.
- Enforce strong password policy and Firebase's built-in abuse protections (sign-in throttling, leaked-credential checks where available).
- Support session revocation (sign-out everywhere) via `revoke_refresh_tokens`.

**Anti-patterns explicitly avoided:** trusting a client-sent `uid`/`email`; using Firebase only on the client; long-lived custom JWTs; storing tokens in cookies without `Secure`/`HttpOnly`/`SameSite`.

---

## 4. Authorization & Data Isolation

This is the **#1 risk** for a multi-tenant app, so it gets two independent layers.

### 4.1 Server-side authorization (primary)
- The authenticated `uid` comes **only** from the verified token (§3).
- Every Firestore read/write is scoped under `sellers/{uid}/…`. The backend never accepts a `uid`/owner field from the client; it sets `owner_uid = decoded["uid"]`.
- Resource ownership is checked on every access: fetching `skus/{skuId}` confirms the doc lives under the caller's `uid` (or carries `owner_uid == uid`). Mismatch → `404` (not `403`, to avoid confirming existence).

```python
# Pattern: never trust client-supplied ownership
async def get_owned_sku(sku_id: str, user = Depends(get_current_user)):
    sku = await repo.get_sku(user["uid"], sku_id)   # scoped query
    if sku is None:
        raise HTTPException(404, "Not found")
    return sku
```

### 4.2 Firestore Security Rules (defense-in-depth)
Deny-by-default; owner-only reads; **clients never write** (all writes go through the backend Admin SDK, which validates input and enforces quotas). See `infra/firestore.rules` (full rules in [`BUILD_PLAN.md`](./BUILD_PLAN.md) §6). Rules are **unit-tested with the Firestore emulator**.

### 4.3 IDOR prevention summary
- IDs are not authorization. Ownership is always re-checked server-side.
- Prefer unguessable IDs (Firestore auto-IDs / UUIDs) as a minor extra hurdle — but never rely on obscurity.
- Object keys in B2 are content-addressable (hash-derived) and access is only via presigned URLs (§8), so knowing a key grants nothing.

---

## 5. Secrets & Key Management

| Secret | Where it lives | Scope / least privilege |
|---|---|---|
| Backblaze B2 app key | Render secret env | Scoped to the **single** bucket; no `listAllBuckets`/account-wide rights. |
| Provider API keys (GMI/OpenAI/…) | Render secret env | Per-provider; rotated; usage-capped where the provider allows. |
| Firebase Admin service account | Render **secret file** (`/etc/secrets/…`) | Backend only; never in client or repo. |
| Firebase **web** config | Frontend env (public by design) | Locked via Auth authorized domains + API-key referrer restrictions. |

**Rules**
- **Nothing secret in the repo.** `.gitignore` covers `.env*`, service-account JSON, build artifacts. Pre-commit **secret scanning** (`gitleaks`) + GitHub push protection.
- **Nothing secret in the browser.** Only the Firebase web config ships to the client; all generation/storage happens server-side.
- **Nothing secret in logs or manifests** (§11, §15).
- **Rotation:** rotate all keys before the public demo and again after (demo videos/screens can leak). Document rotation steps in the runbook.
- **Separation:** distinct Firebase projects + B2 buckets/keys for dev vs. prod.

---

## 6. Input Validation & Upload Security

User uploads (product photos) are the largest untrusted-input surface.

**File validation (server-side, before storing or processing):**
- **Type by content, not extension or `Content-Type`.** Sniff magic bytes / use Pillow's verified decode; accept only an allowlist (`jpeg`, `png`, `webp`, `heic→transcode`).
- **Size caps** (e.g., ≤ 25 MB) enforced at the proxy/app layer; reject early.
- **Dimension & pixel caps** to stop **decompression bombs** (`Image.MAX_IMAGE_PIXELS`); wrap decode in a try/except and reject malformed images.
- **Re-encode** uploads to a normalized format. This neutralizes most polyglot/embedded-payload tricks and **strips metadata**.
- **Strip EXIF/GPS** on ingest (privacy — phone photos carry location). Keep only what's needed.
- **Filenames are untrusted:** never use client filenames for storage paths; keys are hash-derived (content-addressable), eliminating path traversal.

**Other input validation:**
- Validate all JSON bodies with Pydantic (strict types, length limits) — titles, descriptions, style lists, marketplace enums.
- **Prompt-injection awareness:** user text (product descriptions) feeds LLM/image prompts. Treat it as data: constrain with templates, cap length, and never let user text alter system instructions, tool use, or storage targets. Don't reflect raw model output into privileged operations.
- Reject requests for unknown providers/models; the provider/model set is a server-side allowlist (`originshot_pipelines/registry.py`).

---

## 7. Content Safety & Moderation

A generative product can be abused to create disallowed content; moderation is both a safety and a brand/legal requirement.

- **Input moderation:** screen uploaded images (and text) for disallowed content (CSAM — zero tolerance, reported per law; explicit/violent content; obvious illegal goods) using a moderation model/provider before generation.
- **Output moderation:** screen generated images/video before they're shown or exported; quarantine and log violations.
- **On-model / likeness safeguards:** on-model shots must not target real identifiable individuals without consent; restrict to synthetic models and block prompts naming real people (anti-deepfake).
- **IP/trademark guardrails:** discourage generating counterfeit/branded logos; surface a usage-policy reminder. (OriginShot is for *your* products.)
- **Acceptable Use Policy** presented at sign-up; repeat violations → account suspension.
- **Audit trail:** moderation decisions logged; provenance manifest records what was generated (supports takedown/repudiation handling).

---

## 8. Storage Security (Backblaze B2)

- **Private bucket.** No public/anonymous access. The bucket is never browsable.
- **Access via short-lived presigned URLs only** (e.g., 5–15 min TTL), generated per object per request after authorization. URLs are not persisted as "public" fields in Firestore.
- **Least-privilege app key** scoped to the one bucket (read/write/delete on that bucket only).
- **CORS** restricted to the app's exact origin(s); no `*`.
- **Encryption in transit** (TLS to B2) and **at rest** (B2 SSE).
- **Public vs. private separation:** the public `/verify` flow exposes only integrity + non-sensitive lineage, never private media or prompts. If a public "verified sample" is ever shown, it's an explicit, separate, opt-in object.
- **Immutability for originals (integrity):** consider B2 **Object Lock / retention** on uploaded originals so the authentic source can't be silently altered — reinforcing the provenance guarantee.
- **Lifecycle & retention:** define retention; deletion path wired to user account deletion (§12).
- **Backups/versioning:** B2 file versioning on; documented restore procedure.

---

## 9. API Security

- **HTTPS only**, HSTS enabled (Render/Vercel provide TLS). No mixed content.
- **Auth on every route** except `/healthz` and the public `/verify/*` (§3–§4).
- **CORS allowlist** = exact frontend origin(s); credentials handling explicit; preflight locked down.
- **Security headers** (via middleware): `Content-Security-Policy` (restrict script/connect/img sources), `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY` / `frame-ancestors 'none'`, `Referrer-Policy: strict-origin-when-cross-origin`, `Strict-Transport-Security`, `Permissions-Policy`.
- **Rate limiting** per user and per IP (e.g., `slowapi`/Redis) on auth, upload, and generate endpoints.
- **Request size limits** at the proxy and app layers (reject oversized bodies early).
- **Idempotency** on `generate` (idempotency key) to avoid duplicate paid jobs on retries.
- **No verbose errors to clients.** Catch-all handler returns generic messages + a correlation ID; stack traces and provider errors go to server logs only.
- **Input/output schemas** strictly typed (Pydantic) on every endpoint.

---

## 10. Abuse & Denial-of-Wallet Controls

Because each generation calls a **paid** provider, abuse is a *financial* attack, not just a load problem.

- **Per-user quotas:** daily/monthly generation caps by plan; checked **before** enqueuing a job (fail closed).
- **Rate limiting & concurrency caps:** max in-flight jobs per user; global concurrency ceiling.
- **Cost budgets & alerts:** estimate per-job cost via the Genblaze `ModelRegistry` pricing; track spend per user/day; alert and auto-throttle on spikes.
- **Provider-side limits:** set spend caps/budgets on provider accounts where supported (second line of defense).
- **Abuse heuristics:** flag rapid-fire, repetitive, or policy-violating requests; throttle or suspend.
- **Resolution/duration ceilings** in production defaults to bound worst-case cost (e.g., 5-sec video, capped megapixels).
- **CAPTCHA / App Check (optional):** Firebase **App Check** to ensure requests originate from the genuine app, reducing scripted abuse.

---

## 11. Provenance & Integrity Security

Provenance is OriginShot's trust feature, so its own security is in scope.

- **Integrity:** every generated asset carries a SHA-256 Genblaze manifest; `verify()` detects tampering. Originals are hash-anchored at upload.
- **Redaction via `EmbedPolicy`:** public-facing manifests **redact prompts/params** and any sensitive fields so the `/verify` endpoint can't leak business-sensitive prompts or PII. Pointer-mode/sidecars used where appropriate.
- **No secrets in manifests:** ensure provider keys, internal IDs, or user PII are never embedded.
- **Anti-forgery of "authentic" status:** the "authentic vs. AI" determination is computed **server-side** from our records (the original's hash + lineage), not asserted by the client. The public verify result is read-only and derived from stored, integrity-checked data.
- **Tamper-evident originals:** optional B2 Object Lock on originals (§8) so "this is the real photo" can't be quietly rewritten.
- **Replay safety:** `genblaze replay` reruns are themselves authenticated and quota-counted (a replay is still a paid generation).

---

## 12. Privacy & Compliance

- **Data minimization:** collect only what's needed (account email + the media users choose to upload). Strip EXIF/GPS on ingest.
- **User rights (GDPR/CCPA):**
  - **Export:** endpoint to download a user's data (SKUs, assets, metadata).
  - **Deletion / right to erasure:** account deletion cascades to Firestore docs **and** B2 objects (originals + generated + manifests), with a documented, verifiable purge.
- **Retention policy:** defined and disclosed; inactive-data lifecycle on B2.
- **Subprocessors & DPAs:** document the data path through Backblaze, Firebase/Google, Render, Vercel, and generation providers; rely on their DPAs; disclose in the privacy policy. Be explicit that uploaded images are sent to third-party generation providers.
- **AI-content transparency (EU AI Act & marketplace rules):** AI-generated/edited media is disclosed via the provenance manifest and UI labels — a compliance *feature*, not just an obligation.
- **Legal pages:** Privacy Policy, Terms of Service, and Acceptable Use Policy published; cookie/analytics consent if any non-essential tracking is used.
- **Region awareness:** document data residency (B2 region, Firestore location); choose regions deliberately.

---

## 13. Dependency & Supply-Chain Security

- **Pinned dependencies + lockfiles** (`pip`/`uv` lock, `package-lock.json`).
- **Automated scanning:** `pip-audit` + `npm audit` in CI; **Dependabot** (or Renovate) for updates.
- **Minimal footprint:** only the Genblaze provider extras actually used; fewer deps = smaller surface.
- **Provider SDK trust:** Genblaze and provider packages installed from official sources (PyPI `genblaze*`, official provider SDKs); verify versions.
- **SBOM** generated for the submission (nice-to-have, signals maturity).
- **CI hygiene:** least-privilege CI tokens; no secrets echoed in build logs; protected default branch.

---

## 14. Infrastructure & Deployment Security

- **Environment separation:** distinct dev/prod Firebase projects, B2 buckets/keys, and provider keys.
- **Render:** secrets via secret env + secret files; private networking between web and worker where possible; HTTPS enforced; minimal exposed ports; pinned base image in `Dockerfile.backend`; run as non-root.
- **Vercel:** environment variables scoped per environment; preview deployments don't get production secrets; restrict who can read env.
- **Firebase:** Security Rules deployed via CI; Admin SDK only on the backend; App Check optional; authorized domains locked to prod + known preview domains.
- **B2:** as in §8 (private, least-privilege key, CORS, versioning, optional Object Lock).
- **Network/DDoS:** rely on platform protections; optional Cloudflare/WAF in front; rate limiting at the app (§9).
- **Backups & DR:** Firestore export schedule; B2 versioning; documented restore runbook.

---

## 15. Logging, Monitoring & Incident Response

- **Audit logging:** auth events (sign-in/up, token revocation), generation jobs (who/what/when/cost), asset access, moderation decisions, and admin actions — with a correlation ID.
- **No secrets/PII in logs:** scrub tokens, keys, raw prompts, and emails; log identifiers (`uid`, `run_id`), not contents.
- **Monitoring & alerts:** error-rate and latency alerts; **cost/usage spike alerts** (denial-of-wallet early warning); auth-failure spike alerts; provider-failure/fallback-rate dashboards.
- **Incident response plan:**
  1. **Detect** (alert/report) → 2. **Contain** (revoke keys/tokens, disable abused account, throttle) → 3. **Eradicate** (rotate secrets, patch) → 4. **Recover** (restore from B2 versions/Firestore export) → 5. **Review** (post-mortem).
- **Breach notification:** documented obligations (GDPR 72-hour) and a contact path.
- **Key compromise runbook:** step-by-step rotation for each credential class (§5).

---

## 16. Secure SDLC

- **Pre-commit hooks:** `gitleaks` (secrets), formatters/linters, basic checks.
- **Code review** required on the default branch; branch protection on.
- **SAST/linting** in CI (e.g., `bandit` for Python, ESLint security rules).
- **Tests include security cases** (§ below and [`BUILD_PLAN.md`](./BUILD_PLAN.md) §14): authz/IDOR, upload rejection, quota enforcement, Firestore-rule unit tests on the emulator.
- **Threat-model review** at each milestone; this doc updated when the architecture changes.
- **Dependency review** before adding any new package.

---

## 17. Pre-Launch Security Checklist

> Complete **before** the live URL goes public / before submission (Week 5–6). Each item maps to a section above.

**Auth & Access**
- [ ] All routes (except `/healthz`, `/verify/*`) reject missing/invalid tokens (401).
- [ ] `uid` derived only from the verified token; no client-supplied owner fields trusted.
- [ ] User A cannot read or write User B's SKUs/assets/jobs (manual + automated IDOR test).
- [ ] Firestore rules deployed (deny-by-default, owner-only) and **emulator-tested**.
- [ ] Email verification enforced for mutating actions; session revocation works.

**Secrets**
- [ ] No secrets in repo; `gitleaks` clean; push protection on.
- [ ] B2 app key scoped to one bucket; provider keys least-privilege; service account backend-only.
- [ ] No secret/PII in client bundle, logs, or manifests.
- [ ] Keys rotated before and after the public demo.

**Uploads & Content**
- [ ] Magic-byte type allowlist; size/pixel caps; decompression-bomb guard; re-encode + EXIF/GPS strip.
- [ ] Input and output moderation active; CSAM zero-tolerance path defined.
- [ ] Hash-derived storage keys (no path traversal); client filenames untrusted.

**Storage**
- [ ] Bucket private; access only via short-TTL presigned URLs; CORS = app origin.
- [ ] Encryption at rest + TLS; versioning on; (optional) Object Lock on originals.

**API & Abuse**
- [ ] HTTPS/HSTS; CSP + security headers set; CORS allowlist.
- [ ] Rate limits + per-user generation quotas + concurrency caps enforced (fail closed).
- [ ] Cost/usage alerts wired; resolution/duration ceilings set; idempotency on `generate`.
- [ ] Generic client errors + correlation IDs (no stack traces leaked).

**Privacy & Ops**
- [ ] Data export + account deletion (Firestore + B2 purge) implemented and tested.
- [ ] Privacy Policy, ToS, AUP published; AI-disclosure labels live.
- [ ] `pip-audit` / `npm audit` clean; dependencies pinned; Dependabot on.
- [ ] Audit logging on; cost/error/auth alerts on; incident & key-rotation runbooks written.
- [ ] dev/prod environments fully separated.

---

## 18. Threat → Control Summary

| Threat | Control(s) | Section |
|---|---|---|
| Stolen/forged identity | Firebase ID-token verification, revocation, email verification | §3 |
| Cross-user data access (IDOR) | Server-derived `uid` + ownership checks + deny-by-default Firestore rules | §4 |
| Secret leakage | Server-only secrets, secret scanning, least privilege, rotation | §5, §13 |
| Malicious upload (bomb/polyglot/path) | Type/size/pixel validation, re-encode, hash keys | §6 |
| Disallowed generated content / deepfakes | Input + output moderation, likeness/IP guardrails, AUP | §7 |
| Public/over-permissive storage | Private bucket, presigned URLs, scoped key, CORS | §8 |
| Injection / verbose errors | Pydantic validation, prompt-injection handling, generic errors | §6, §9 |
| Denial-of-wallet / abuse | Quotas, rate limits, concurrency caps, cost alerts, App Check | §10 |
| Provenance tampering / prompt leak | Manifest integrity + server-side authenticity + EmbedPolicy redaction | §11 |
| Privacy violation | Minimization, EXIF strip, export/delete, DPAs, disclosure | §12 |
| Supply-chain compromise | Pinned deps, scanning, SBOM, official sources | §13 |
| Misconfiguration / leaked ops secret | Env separation, secret files, least privilege, monitoring, IR | §14, §15 |

---

## 19. Responsible Disclosure

- Provide a `SECURITY.txt` / contact (e.g., `security@originshot.app`) for reporting vulnerabilities.
- Commit to acknowledging reports promptly and not pursuing good-faith researchers.
- Track and remediate reported issues with severity-based SLAs.

---

*Security is a feature of OriginShot, not a phase. If the architecture changes, update this document first, then the build.*
