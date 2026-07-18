# Release announced as v0.5.0 publishes to PyPI as `genblaze` 0.4.3 — `pip install genblaze==0.5.0` fails

**Context:** the hackathon announcement email ("genblaze v0.5.0", 2026-07-17) and the
GitHub release tagged `v0.5.0`.

## Summary

The GitHub release is tagged **v0.5.0** (published 2026-07-17T16:15:52Z), but the umbrella
package on PyPI is **0.4.3** (uploaded 2026-07-17T16:19:13Z, ~3 minutes later). There is no
`genblaze` 0.5.0 on PyPI:

```
$ pip install "genblaze[gmicloud,video,parquet]>=0.5,<0.6"
ERROR: Could not find a version that satisfies the requirement genblaze<0.6,>=0.5
       (from versions: 0.2.3, 0.3.0, 0.3.1, 0.3.2, 0.4.0, 0.4.1, 0.4.3)
```

The announcement's own upgrade instructions (`pip install genblaze[all]`) do work, because
they don't name a version — but anyone who pins the announced version, or who checks that
they're on "0.5.0" before reporting a bug, hits a wall.

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

Publish the umbrella as `0.5.0` (or retag the GitHub release to `v0.4.3`) so the announced
version, the tag, and the installable artifact agree. It would also help to state the
resolved sub-package versions in the release notes, since those are where the changes
actually live.

## Also

The announcement email links feedback to `https://github.com/backblaze/genblaze/issues`,
but the repository is at **`backblaze-labs/genblaze`** — the former 404s.
