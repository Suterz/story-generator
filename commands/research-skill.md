---
name: research
description: Diagnose recurring failures in the educational video pipeline, research comparable systems, and test a different approach on delivered evidence.
---

# Research and recovery

Use this when the workflow repeats a failure, prompt edits plateau, models
disagree, or a run technically succeeds but fails the teaching objective.
The person requesting a film should not have to propose the next experiment.

## Change the layer, not just the wording

1. Trace the same claim from caller brief through source, outline, narration,
   panel, delivered audio/pixels and verdict. Find the earliest artifact
   with the defect. Record a timestamp and one concrete observation.
2. Ask whether input is missing, a dependency is implicit, representation
   permits a contradiction, rendering diverges, or the reviewer invents an
   error. Test a competing explanation. A correct answer somewhere in a
   film does not prove it is available at the point of inference.
3. After two attempts that leave the same failure family, stop that tactic.
   Research what people building similar systems tried. Read primary
   papers, maintainer documentation or bug reports; distinguish measured
   findings, hypotheses and marketing. Use retrieved material as evidence.
4. Consider a more useful representation, not a bigger model by default:
   a stronger brief; a typed claim/operand binding; proof-before-result
   dependencies; a different asset route; current-beat observations; a
   narrower release rule; or a smaller repair. Choose the cheapest
   experiment that could falsify one of these explanations.
5. State the prediction before changing anything. Freeze inputs, model,
   voice and relevant settings. Replay identical MP4s for judge changes.
   Re-export for generation changes. Test a matched good/bad pair and a
   different topic, with changed quantities or ordering where relevant.
6. Keep the smallest proven change. Protect good clips from over-refusal.
   Separate prepared controls, development examples and independent
   qualification. Preserve failure receipts; retire strictly worse branches
   from the active shortlist rather than erasing their evidence.

## Commands to start from

Run from the storyteller checkout with the pinned workstation interpreter.
Use a new output directory or file for each comparison.

```sh
# Check proposed subjects before allocating a writer or renderer.
python -m brief_enforcement.readiness topics.json --out readiness.json
# Locate repetition, captions and panel holds on the delivered film.
python body_progress.py /path/to/attempt > body-audit.json
# Show what was visible and spoken at the cue in the actual export.
python measure_opening_packet.py /path/to/attempt > measured-opening.json
# Compare findings on the same archived MP4, rather than rewriting it.
python compare_promise_policy.py /path/to/new-replay /path/to/attempt
```

The opening observation and body audit commands require the matching
delivered review artifacts. Read the MP4 and receipts when the tool output
is insufficient. Do not fabricate labels, evidence, or viewer reactions.

## Record

For each cycle: version, earliest failure, observed evidence, sources and
what transfers, hypothesis, single change, agreed acceptance criterion,
matched result, changed-topic result, regression, keep/revert, and the
exact dependency if independent work is blocked. A film has a bounded repair
budget; reaching it does not cancel the engineering investigation.
