# Daily-run staging

`storygen.py run` dispatches `schema_version: daily/1` to `daily.py`. Its
`BRIEF` is the input schema. This path is opt-in. It produces an immutable
first-outcome record per run directory and uses the staged `/v2/episodes` API.
There is no production promotion. Do not use this path for unattended
publication until blind qualification passes.

## Staging configuration

- `DAILY_FREEZE`: file hashed into the local decision. For scored use, have
  `daily_batch.py` verify repository commits and the runtime artifact inventory.
- `DAILY_FETCH_PROGRAM`: optional executable `daily_fetch.py`. Leave unset for
  offline runs. The broker accepts only exact HTTPS publisher hosts configured
  in `DAILY_PUBLISHERS` (JSON mapping host to publisher), no redirects. Set a
  contact-bearing `DAILY_HTTP_AGENT`. Public Crossref discovery is opt-in per
  claim via `public_discovery`; candidate pages may also be supplied. The
  broker handles HTML and plain text. No PDF extraction or paid provider is
  wired. Set `DAILY_CACHE_APPROVED=1` only where publisher retention is cleared;
  `DAILY_SOURCE_CACHE` selects the external cache root.
- Frames: `DAILY_ASSET_CACHE` holds `catalog.json` and originals by SHA-256.
  The catalog is trusted operator configuration, not model or caller input.
  It records item-level commercial editorial rights and credit separately
  from content review. `DAILY_ASSET_FETCH_PROGRAM` may fetch a missing,
  hash-pinned original via `daily_fetch_asset.py` with `DAILY_IMAGE_HOSTS`.
  `DAILY_IMAGE_DISCOVERY` can enable `daily_commons.py`, which considers at
  most three Commons items, verifies the original file page revision and
  admits only explicit CC0/CC BY own-work metadata. Only compositions passing
  the separate image checks are indexed for reuse. Coverage is deliberately
  narrow. A required authentic visual has no synthetic fallback.
- `DAILY_FRAMES_REPO`, `DAILY_VIDEO_REPO`, `DAILY_RUNTIME_ROOT` and
  `STORY_VISION_MODEL` select local speech and vision workers. Use the same
  GPU lease for story, frames and review. Keep service stores and ports
  separate from the production and long-form qualification instances.

## Scoring and publication

`daily_calibrate.py run` accepts a folder of opaque cases, each with
`video.mp4` and `packet.json` containing `mp4_sha256`, `objective`, `evidence`
and `windows` (start/end seconds and visual inspect time). Historical
identifiers, judgments and labels must be outside that folder. Its separate
`score` command consumes the labels only after predictions are locked. These
window controls do not qualify the full-film reviewer by themselves.

For `daily_batch.py`, a separate evaluator prepares five `01.json` through
`05.json` files and a seal containing `briefs` (slot to file SHA-256) plus an
`expected_outcome_commitment` (hash of the separately guarded manifest).
The batch freeze's `repositories` maps `story`, `frames` and `video` to
`path` and `commit`; `files` maps absolute runtime/weight/config/cache files
to their hashes; `runtime` contains `writer`, `weights`, `llama`, `lease`,
`validator_python` and `video_url`. Freeze once, after calibration and before
the pilot, and include the external service launch configurations and approved
cache inventory in the freeze. Start from an enforced loopback-only environment
with any optional fetch broker separately isolated. A negative endpoint probe
is a startup control, not proof of complete isolation. Close OpenCode before
releasing the queue. The batch requires a new output directory.

`daily_publish.py` takes a locally staged result store, a separate independent
audit keyed by two-digit case slots (status, reason, MP4 and freeze hashes),
and a new destination such as `Autonomous Daily Run/Watch first`. It requires
both acceptance records, verifies hashes and playback, and stages the media,
playlist, review key and attribution before exposing that directory.
