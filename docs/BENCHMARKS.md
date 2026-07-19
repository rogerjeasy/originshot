# Measured performance

Every number here came from a real run against real GMI Cloud models and the real Backblaze
B2 bucket, on the dates given. Sample sizes are small and are stated for each row rather than
rounded away — three runs is three runs, and presenting it as a smooth "average" would imply
a confidence the data does not carry.

Nothing on this page is extrapolated. Where a figure could not be measured, it says so.

## Wall-clock

| What | Measured | n | When |
|---|---|---|---|
| **Studio pack** (1 image, incl. QA scoring) | **74.6s** and **126.5s** | 2 | 2026-07-19 |
| **Two products, concurrently** (Catalog Mode, concurrency 2) | **128s** wall clock against **201s** of summed per-product work | 1 | 2026-07-19 |
| **Hero video** (Kling image→video, 960×960, 5.1s clip) | **4m 14s** | 1 | 2026-07-18 |
| **QA vision scoring** (one image pair, `x-ai/grok-4.5`) | **3.8–8.8s** | 4 | 2026-07-19 |
| **Dispute comparison** (Resolve, one image pair) | **10.1–18.6s** | 4 | 2026-07-19 |

The concurrency row is the one worth reading twice: 128s of wall clock for 201s of work is
the entire argument for Catalog Mode, and it is a measurement rather than a projection.

The two studio-pack timings differ by 52s because the slower one took a **QA retry** — the
agentic evaluate→retry loop regenerated a style whose first attempt failed scoring. That
spread is the honest picture of a pipeline with a quality gate in it, not noise to be
averaged out.

### Not yet measured

**Full default pack (studio + lifestyle, 3 images).** Attempted 2026-07-19; the runs
returned HTTP 402 `Insufficient credits` from GMI Cloud partway through, so there is no
figure to report. It will land here once the provider balance is topped up. A projection was
deliberately not substituted.

## Cost

| | |
|---|---|
| List-price estimate, default pack (studio + lifestyle, 3 images) | **$0.12** |
| List-price estimate, studio only (1 image) | **$0.04** |
| List-price estimate, hero video | **$0.50** |
| **Provider-billed cost** | **Not available — see below** |

`Step.cost_usd` comes back as **0** from GMI Cloud on runs that were genuinely billed, so the
ledger settles those jobs at zero and the "actual" column in analytics has nothing real to
show for them. The dual-sourced cost design exists precisely so this shows up as a labelled
absence instead of a list-price estimate wearing an authoritative badge. See the Known
Limitations section of the README.

The comparison the product actually rests on does not depend on that gap:

| | Per product |
|---|---|
| Professional product photography | **$25–150** |
| OriginShot, list-price estimate | **$0.12** |

Even taking the estimate as an upper bound and allowing for retries, that is a difference of
more than two orders of magnitude. The claim being made is about the order of magnitude, not
about the third decimal place.

## Reproducing these

The timings above come from the app's own instrumentation, not a stopwatch: every job records
`started_at`, `finished_at` and `duration_ms` per step (`JobStep` in `backend/app/models.py`),
and Catalog Mode records `duration_ms` per product. So any run you do yourself reports the
same numbers this page does.

```bash
# One pack, timed per style — the numbers appear in the job document.
curl -X POST .../api/skus/<id>/generate -d '{"styles":["studio","lifestyle"]}'
curl .../api/jobs/<job-id>          # steps[].duration_ms, qa_attempts

# A catalog run — per-product duration and the concurrency lanes used.
curl .../api/batches/<batch-id>     # items[].duration_ms, concurrency
```

## Caveats worth stating

- **Small samples.** Nothing here has enough runs to quote a median with meaning; the ranges
  are shown instead.
- **Provider variance dominates.** These are wall-clock times through a third-party queue.
  The same pack at a different hour will differ, sometimes considerably.
- **The API host is a free-tier instance** that sleeps after ~15 minutes idle. A first
  request after a sleep adds roughly 50s of cold start, which is not included above because
  it measures Render, not this pipeline.
