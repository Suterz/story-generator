# Workstation runs and evidence

The first 20 briefs in `benchmark/first20.tsv` are development cases. The
`provenance` column identifies topics already used by the renderers. Expectation
columns are authored independently and not sent to the model. These cases
have no role in a future sealed claim. Keep near variants of the same mechanism
in the same partition. The intended expanded split is 140 development, 30
validation and 30 genuinely sealed cases; do not create a sealed score before a
single frozen build passes the first 20.

For a complete run against the staged services:

```sh
python -B sweep.py "$RUN_DIR" \
  --frames "$FRAMES_REPO" --video "$VIDEO_REPO" --model qwen
python -B inspect_run.py "$RUN_DIR" --ffmpeg "$FFMPEG" --ffprobe "$FFPROBE"
```

Run these inside a named, detached tmux session. Resume with exactly the
same working tree and arguments. `freeze.json` pins the three repository
commits and case IDs. Each case saves the original brief, independent
expectation, editorial plan, raw generation attempts, validated request,
receipt, service status, manifest and downloaded MP4 hash. Stop if an
interrupted writer receipt cannot be reconciled; do not secretly generate a
replacement. The renderer is reconciled by GET using the recorded idempotency
key. Keep a new store for a new build.

`inspect_run.py` decodes the start, cue boundaries, meaningful caption starts
and final frame. These are candidates for independent adjudication alongside
the original expectation, actual MP4 and unprompted speech evidence. Do not
count an encoded video as correct until every material frame and transition
is checked. Store the verdict and explanation next to the media. Keep first
candidate and automatic repair passes separate and retain all other outcomes.

When debugging a writer, start with the earliest failure in the original
brief-to-MP4 path. For example, raw JSON wrapping the script in an object was
a runtime/grammar configuration problem; a rewritten phrase that the speaker
never says was an authoring-interface problem. A reverse price comparison is a
content error even if the generated request is valid. Keep the before request
and script, an after result on the original brief, and a different transfer case.
