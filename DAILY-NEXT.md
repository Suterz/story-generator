# Ordinary daily briefs

The public command is `storygen.py run BRIEF --out RUN --model mistral-small
--voice heart`. An ordinary JSON brief uses `schema_version: daily/2` and
requires only topic, audience and objective. Optional `facts` are substantive
caller facts as strings. Optional `constraints`, `misconceptions`, `transfer`,
`signature`, and `min_ms` carry editorial scope. A one-off baseline adapter
`--daily` reads an unstaged `episode/1` input without weakening the existing
staged route.

Use separate stores and the matching frame and video worktrees. Configure
`DAILY_FREEZE`, `DAILY_FRAMES_REPO`, `DAILY_VIDEO_REPO` and optionally
`DAILY_DRAFT_GALLERY`; `DAILY-RUN.md` describes fetchers and worker pins.
The workflow records `attempt-01/`, the preserved `first-outcome.json`, and
`terminal-outcome.json`. At most one automatic whole-film retry is allowed
for authoring, alignment, or an uncertain local editorial judgment. Attempts
retain distinct paths and submission keys. Model schema retries are also
recorded. No automatic retry bypasses an essential evidence or rights failure.
Draft delivery needs an accepted local verdict with matching media and
manifest hashes, credit records, and a full audio/video decode. It does not
require a human audit. The existing audited publisher is separate.

Development diagnostics do not qualify the pilot. Keep candidate selection,
rights checks, and human watchability assessments separate from automated
verdicts. The worker isolation test and independent held-back calibration
must pass before releasing the five sealed topics. A negative endpoint check
in the batch is a preflight, not a containment mechanism.
