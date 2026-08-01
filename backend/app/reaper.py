"""Stale-job reaper — the cleanup `worker._run_job`'s `finally` cannot perform.

`_run_job` reconciles every outcome it can *observe*: success, partial, and any exception the
run raises are all settled in a `finally`. That covers everything except the one failure where
no Python code runs at all — the process dying underneath the job. On the deployed free-tier
instance (512 MB, 0.1 CPU) that is not hypothetical: an OOM kill during an ffmpeg mux, or a
platform restart, takes the interpreter with it. Generation runs inline via
`BackgroundTasks`, so the in-flight job dies with the process and *nothing* ever writes its
terminal status.

The observable result is the worst shape a job can have:

  * `status` stays `running` forever — the studio shows a spinner that never resolves, which
    reads to a user as "your product is still generating", not "this run is gone"; and
  * `credits_held` stays outstanding forever — the money is debited from the spendable
    balance and never refunded, so the balance permanently understates what the user has.

So a job's terminal status cannot depend solely on its own process. This module re-derives it
from the clock, which survives the crash.

**Lazy, not scheduled.** Reaping runs on read (`GET /jobs/{id}`, the SSE stream) and in the
Auditor's periodic pass, rather than from a timer of its own. A hung job matters exactly when
someone looks at it, the read path is where the user is already waiting, and this keeps the
deployment free of a second always-on process — the same reason generation itself runs inline.

**The deadline is the job's own budget, not a flat timeout.** Each style already carries a
provider timeout (`image_timeout_seconds`, `video_timeout_seconds`, `audio_timeout_seconds`);
a job is stale only once every style it asked for has had its full budget plus
:data:`STALE_MARGIN_SECONDS` of overhead. A five-style pack with a video step therefore gets
minutes longer than a single studio shot, and a *live* job is never reaped out from under a
provider that is simply slow — the failure mode that would make this cure worse than the
disease.

**Settlement refunds the whole hold.** A reaped job's `cost_actual` was never written (the
process died before the patch), and assets do not carry a `job_id`, so there is no way to
attribute salvaged work back to this job after the fact. Refunding in full is the honest
resolution of that uncertainty and matches the rule the ledger already follows — a user is
never charged for a failure they got no assets from. It can, in principle, refund a run the
provider did bill for; that is a cost we choose to absorb rather than charge for work we
cannot prove was delivered.
"""
from __future__ import annotations

import logging

from .config import get_settings
from .models import JobStatus, StepStatus, utcnow
from .repo import get_repo

log = logging.getLogger("originshot.reaper")

# Non-terminal statuses. A job in any of these is still claiming to be in progress.
_LIVE = {JobStatus.queued.value, JobStatus.running.value}

# Overhead allowance on top of the summed provider budgets: sink upload, manifest embed, QA
# scoring, ledger append and the settle write all happen outside the provider call. Generous
# on purpose — reaping a job that was about to finish is strictly worse than reaping it a
# couple of minutes late, because the late reap is only ever cleaning up after a crash.
STALE_MARGIN_SECONDS = 180

# Floor, for a job whose `requested_styles` is empty or unrecognised. Long enough to clear the
# slowest single step so a malformed job document can never shorten a real run's leash.
MIN_DEADLINE_SECONDS = 900

_REAPED_ERROR = (
    "Run did not complete: the worker stopped before this job finished (most likely the "
    "instance restarted or ran out of memory mid-run). No partial charge was made — the "
    "full credit hold has been refunded. Please try again."
)


def _style_budget(style: str) -> int:
    """The provider timeout this style is allowed to consume, in seconds."""
    s = get_settings()
    if style == "video":
        return s.video_timeout_seconds
    if style == "voiceover":
        # Script hop + TTS, then the narrated-video mux, which runs on the video budget.
        return s.audio_timeout_seconds + s.video_timeout_seconds
    return s.image_timeout_seconds


def deadline_seconds(job: dict) -> int:
    """How long `job` may run before it is considered abandoned."""
    styles = [str(s) for s in (job.get("requested_styles") or [])]
    budget = sum(_style_budget(s) for s in styles)
    return max(MIN_DEADLINE_SECONDS, budget + STALE_MARGIN_SECONDS)


def _age_seconds(job: dict) -> float | None:
    """Seconds since the job last plausibly made progress, or None if it can't be dated.

    Measured from `started_at` when the run began, else `created_at` — a job that died while
    still `queued` never got a `started_at` and would otherwise be un-reapable.
    """
    stamp = job.get("started_at") or job.get("created_at")
    if stamp is None:
        return None
    try:
        return (utcnow() - stamp).total_seconds()
    except TypeError:
        return None


def is_stale(job: dict) -> bool:
    """True when `job` claims to be running but has outlived its own budget."""
    if str(job.get("status")) not in _LIVE:
        return False
    age = _age_seconds(job)
    return age is not None and age > deadline_seconds(job)


def reap_job(uid: str, job: dict) -> dict | None:
    """Fail one abandoned job and release its hold. Returns the updated job, or None.

    Idempotent by construction: the status write moves the job out of `_LIVE`, and
    `credits_held` is zeroed in the same pass, so a concurrent second reap finds nothing to
    do. Settlement is exception-guarded for the same reason it is in `worker._run_job` — a
    ledger failure must not leave the job stuck `running`, which is the exact condition being
    repaired.
    """
    if not is_stale(job):
        return None

    from . import credits

    repo = get_repo()
    job_id = job["id"]
    held = float(job.get("credits_held") or 0.0)

    # Any step still claiming to be in flight is finished as failed too — a job that reads
    # `failed` while a step underneath it still reads `running` just moves the spinner.
    steps = []
    for step in job.get("steps") or []:
        if str(step.get("status")) in (StepStatus.pending.value, StepStatus.running.value):
            step = {**step, "status": StepStatus.failed.value,
                    "finished_at": utcnow(), "error": "worker stopped before this step finished"}
        steps.append(step)

    updated = repo.update_job(uid, job_id, {
        "status": JobStatus.failed.value,
        "error": _REAPED_ERROR,
        "finished_at": utcnow(),
        "steps": steps,
    })
    log.warning("reaped abandoned job %s (age %.0fs, budget %ds, held $%.4f)",
                job_id, _age_seconds(job) or 0.0, deadline_seconds(job), held)

    if held:
        try:
            credits.settle(uid, job_id=job_id, sku_id=job.get("sku_id") or "",
                           held=held, actual=0.0)
            updated = repo.update_job(uid, job_id, {"credits_held": 0.0}) or updated
        except Exception:  # noqa: BLE001
            log.exception("reaper: settlement failed for job %s (held $%.4f)", job_id, held)

    # Close any live SSE stream still waiting on this job: the terminal status is what ends it.
    try:
        from . import events

        final = repo.get_job(uid, job_id)
        if final:
            events.publish(job_id, final)
    except Exception:  # noqa: BLE001
        pass

    return updated


def reap_one(uid: str, job: dict | None) -> dict | None:
    """Reap `job` if stale, returning whichever version the caller should serve.

    The read-path entry point: hand it what the repo returned and serve the result, so a user
    polling a job that died sees a real `failed` with a refund instead of an endless spinner.
    """
    if not job:
        return job
    return reap_job(uid, job) or job


def reap_user(uid: str, limit: int = 100) -> int:
    """Reap every abandoned job for one user. Returns how many were reaped."""
    reaped = 0
    for job in get_repo().list_jobs(uid, limit=limit):
        if reap_job(uid, job):
            reaped += 1
    return reaped


def reap_all(limit: int = 200) -> int:
    """Global sweep across every user — the Auditor's pass. Returns how many were reaped.

    Each job is reaped under its *own* owner so per-user credit settlement stays correct;
    `list_all_jobs` is a cross-user admin read, which is why this is only ever called from
    the audit path and never from a user-facing route.
    """
    reaped = 0
    for job in get_repo().list_all_jobs(limit=limit):
        owner = job.get("owner_uid")
        if owner and reap_job(owner, job):
            reaped += 1
    return reaped
