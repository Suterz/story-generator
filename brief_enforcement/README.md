# Brief enforcement

An editorial brief specifies what the viewer should learn and what evidence
must be shown to teach it. This package provides a reusable preflight for
subject lists and a production-entry adapter for `storygen.py`.

## Check a subject list or a single brief

From the storyteller checkout, with `jsonschema` installed:

```sh
python -m brief_enforcement.readiness input.json --out readiness.json
```

`input.json` can be one `daily/3` brief or an array of briefs. Only queue
items with `queueable: true`. `needs_input` requires an editorial decision,
`needs_research` requires source work and a subsequent check, and `withhold`
indicates a contradiction or impossible teaching order. `ready` means the
brief passed intake, not that every teaching pattern is renderable or that
the resulting film is publishable. The CLI uses no model or renderer.

Required fields cover audience and prior knowledge, a learnable objective,
intro, lesson, mechanism, result, a transfer question with answer and reason,
supporting facts, tone, delivery constraints and a takeaway. Phase prerequisites
refer to inference IDs established by earlier phases. See `examples/battery.json`
for a complete brief. Keep source provenance with each measurement. Durations
are either hard ranges or targets; a target must not be used to pad narration.

`storygen.py run` dispatches `daily/3` to the same intake. Use
`--require-ready-brief` to enforce it explicitly on submitted files. Existing
production V2 and archived `daily/2` experiments retain their existing routes.
The exact lesson adapter currently executes the supported two-battery
whole-percent comparison; it records a specific withhold for other patterns.
No guessed alternative or permissive render fallback is used. An exact-check
success is a reviewable draft, not an independent editorial verdict.

The reusable boundary is `readiness.py`; `lesson.py` is deliberately the
storyteller/video integration. The topic list checker requires neither a
storyteller server nor access to local inference models.
