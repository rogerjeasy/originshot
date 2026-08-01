# GitHub release tags (v0.5.0, v0.6.0, v0.7.0) have no matching PyPI version — `pip install genblaze==0.7.0` fails

**Context:** the hackathon announcement email ("genblaze v0.5.0", 2026-07-17) and every
GitHub release tagged since.

## Summary

No GitHub release tag from `v0.5.0` onward exists as an installable `genblaze` version. As of
2026-08-01 the two sequences have diverged completely:

| GitHub release | Published | Matching PyPI `genblaze` |
|---|---|---|
| `v0.5.0` | 2026-07-17 | none (PyPI got 0.4.3, ~3 min later) |
| `v0.6.0` | 2026-07-22 | none |
| `v0.7.0` | 2026-07-28 (latest) | none |

PyPI's full history is `0.2.3, 0.3.0, 0.3.1, 0.3.2, 0.4.0, 0.4.1, 0.4.3, 0.4.4, 0.4.5` — it
has never published a 0.5.x, 0.6.x or 0.7.x at all.

```
$ pip install "genblaze[gmicloud,video,parquet]>=0.5,<0.6"
ERROR: Could not find a version that satisfies the requirement genblaze<0.6,>=0.5
       (from versions: 0.2.3, 0.3.0, 0.3.1, 0.3.2, 0.4.0, 0.4.1, 0.4.3, 0.4.4, 0.4.5)
```

The announcement's own upgrade instructions (`pip install genblaze[all]`) do work, because
they don't name a version — but anyone who pins the announced version, or who checks that
they're on "0.5.0" before reporting a bug, hits a wall. This was reported to us as a one-off
at v0.5.0; three releases later it looks systemic, which is why it seems worth raising.

## Why it's worth fixing beyond the version string

The umbrella package only carries dependency floors, so the version number is the *only*
signal about what a participant actually has installed. Two people can both say "I'm on the
v0.5.0 release" while running different `genblaze-core` builds:

```
genblaze 0.4.3  ->  genblaze-core 0.3.6, genblaze-gmicloud 0.3.3, genblaze-s3 0.3.5
genblaze 0.4.0  ->  genblaze-core 0.3.2, genblaze-gmicloud 0.3.1, genblaze-s3 0.3.2
```

A `>=0.4,<0.5` constraint — the natural one to write after the 0.4.0 release — happily
resolves to 0.4.0 and silently keeps all the *old* sub-packages, so none of the streaming
concurrency, manifest-validation, or SSRF/ReDoS hardening in this release reaches the
application. We only noticed because we pinned the floor explicitly to 0.4.3 after finding
this.

## Suggestion

Make the tag and the installable artifact agree in one direction or the other — either publish
the umbrella under the released version number, or tag releases with the version that actually
ships. It would also help to state the resolved sub-package versions in the release notes,
since those are where the changes actually live and they are currently unrecoverable from the
tag alone.

## Also

The announcement email links feedback to `https://github.com/backblaze/genblaze/issues`,
but the repository is at **`backblaze-labs/genblaze`** — the former 404s.
