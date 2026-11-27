# Opening writer and reviewer qualification

### Iterate until convergence

Own the improvement loop: run → inspect the delivered output → diagnose the failure → predict the effect of one change → rerun the matched comparison → test transfer. A failed qualification starts the next development cycle. Compare the brief, plan, assets, decoded pixels, delivered speech and verdict to locate the first error. Keep failed attempts and refusals. Rerun passing controls and unfamiliar transfers before promotion. Retire any qualification case used to tune a change.

One film has a bounded repair budget, separate from the engineering loop. Convergence means a frozen build passes transfer, fresh blinded review, bounded repair and operating gates together. A flat score below target is a plateau. Continue testing concrete causes while possible; record the exact constraint if outside evidence is unavailable.

Each cycle records version, observed failure, root-cause hypothesis, change, predicted and matched results, transfer, regressions, and keep/revert decision.

Retire a strictly dominated instruction from the active lineup: on matched
inputs it improves none of the required measures and is worse on at least
one. Keep its frozen text, commit and receipts so prior results can still be
reproduced. A version that trades better detection for excessive refusal is
not eligible for promotion; resolve the trade-off on fresh cases.

## Comparison contracts

`storygen.py run BRIEF --opening-preview baseline-v1|visible-question-v2`
uses the ordinary `daily/2` input and `/v2/openings`. This stages short
exports independently of full-film production. The baseline outline is
adapted to the common preview format; the full historical baseline is
the opening of the archived battery film. Do not compare that older long
film against a shorter render as if the instruction were the only change.

Opening reviewer `observable-opening-v2` inspects the delivered speech and
decoded images before giving a timed, coded verdict. Its comparison arm is
the old `review_daily.editorial` instruction on identical clip evidence.
Seal labels, clip hashes, tolerance, and rubric before scoring. Never give
the labels to either reviewer. `opening_score.py` checks trace bindings and
separately counts verdict and localization errors. Qualification is 12 bad,
12 good, zero bad accepts, and at most one good withhold; inspect missed
localization separately. Archive replays are development, not qualification.

### Operating modes

- Render openings using the same model, fixed Drama 3 reference, seed,
  services, caption settings and budget. Preserve both MP4s and their
  attempt directories. A preview must be 10–20 seconds; a failure is recorded.
- For a separate network namespace, expose retrieval only through
  `opening_broker.py serve /private/run/broker.sock`. Set
  `DAILY_BROKER_SOCKET` in the worker, and point `DAILY_FETCH_PROGRAM` and
  frames `DAILY_IMAGE_DISCOVERY` to `opening_broker.py`. `DAILY_PUBLISHERS`
  and `DAILY_HTTP_AGENT` belong to the broker. Keep the socket directory
  private. The broker takes scoped publisher/Commons requests, not
  arbitrary HTTP proxy requests.
