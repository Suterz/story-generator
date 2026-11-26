# story-generator

Local English lesson briefs to renderer requests. A brief is a JSON file with
`topic`, `takeaway`, `required_facts`, `audience`, and a named `signature`.
Optionally set `"artwork": "paper"` for diagrams that must draw all visual
evidence with controlled shapes and labels. This does not change other briefs.
See `examples/market/brief.json`. The writer and renderer expose separate
failure evidence; a valid story or playable video has not passed adjudication.
Start with [agent context](agent-context.md) for the tested renderer combination
and the writer's current limitations.

## CommunicationBrief v1

The generic contract is [CommunicationBrief v1](schemas/CommunicationBrief.v1.json).
Supply topic, objective, takeaway and source notes. Audience, tone, language
(`en`), duration (29,999 ms) and signature (`paper`) have default-v1 values.
`fact` means supplied factual authority; use `verbatim` for exact spoken
wording, `constraint` for limits and `note` for unapproved context. The
existing education-shaped JSON is still accepted by the original lesson skill.

```sh
.venv/bin/python -B storygen.py normalize examples/carriage/rough.txt \
  --raw-text --model mistral-small --out "$RUN/rough"
.venv/bin/python -B storygen.py normalize examples/carriage/wayfinding.json \
  --out "$RUN/structured"
```

Structured normalization does not launch a model. Inspect `normalization.json`
for the original input and intent hash, and `provenance.json` for source
excerpts or default origins. Run `write` for the renderer request or `run`
for rendering, with the same native validator options below. A `needs_input`
result is JSON on stdout and in `result.json`; `render_submitted: false`
means nothing was posted to the renderer. Supply the missing information in a
new brief revision and use a new output directory. The initial policy check
is scoped to explicit rule requests; it is not a general fact checker.

The [carriage contract example](examples/carriage/contract-story.json) is a
hand-authored control, separate from what the writer produces. Its choice of
opening, wording and beat count is not imposed on callers. See the
[communication iteration](agent-context/README.md) and
[benchmark rubric](benchmark/communication/RUBRIC.md) for measured results.

## Install on the workstation

Use Python 3.12.3 and install `requirements.lock` into a fresh environment:

```sh
uv venv --python /usr/bin/python3 .venv
uv pip sync --python .venv/bin/python requirements.lock
```

Use the llama.cpp Ubuntu x64 Vulkan release `b6500` (upstream commit
`a7a98e0fffed794396b3fbad4dcdbbc184963645`). Vulkan is available on the tested
4090. Download `llama-b6500-bin-ubuntu-vulkan-x64.zip` from the upstream GitHub
release and verify SHA-256
`ee15538d98808f15d13a474d2554bc708a475e35bf560e1d0d21b9e96bc5f8ea` before
extracting to an external directory. Keep sibling libraries next to the server.
`llama-server --list-devices` should report the NVIDIA device.

Install each candidate with its exact identifiers in `models.json`:

```sh
model=qwen  # alternatively mistral or deepseek
hf download "$(jq -r ".${model}.source" models.json)" \
  "$(jq -r ".${model}.file" models.json)" \
  --revision "$(jq -r ".${model}.revision" models.json)" --local-dir "$MODEL_DIR"
```

`storygen.py` verifies the file against the manifest every time it starts a new
generation. It runs one local model with an 8192-token context and releases the
shared GPU lock before submitting to video. It uses the v4 skill, nested API
schemas, and at most one corrective generation on a concrete validation error.
Keep weights and output stores outside the checkout.

```sh
.venv/bin/python -B storygen.py write examples/market/brief.json \
  --models "$MODEL_DIR" --runtime "$LLAMA_SERVER" --out "$RUN/market-story"
.venv/bin/python -B storygen.py run examples/market/brief.json \
  --models "$MODEL_DIR" --runtime "$LLAMA_SERVER" --video-url "$STAGED_VIDEO_URL" \
  --validator-python "$RENDERER_PYTHON" --frames-repo "$FRAMES_REPO" --video-repo "$VIDEO_REPO" \
  --out "$RUN/market-video"
```

Use the native preflight options together for full contract and phone-label
checks. Without them the CLI warns that it performs schema-only validation.
The writer proposes stories; independently inspect the delivered lesson before
using it.

The staged renderer pair must support `GET /v2/submissions/{key}`. A resumed
directory recovers by GET instead of repeating a submitted render. Case notes,
failure diagnostics, the story, job ID, manifest and returned media hash are
retained. `sweep.py` uses the independent expectations in
`benchmark/first20.tsv`; only the brief fields are given to the writer.
