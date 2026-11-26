# story-generator

Local English lesson briefs to renderer requests. A brief is a JSON file with
`topic`, `takeaway`, `required_facts`, `audience`, and a named `signature`.
See `examples/market/brief.json`. The writer and renderer expose separate
failure evidence; a valid story or playable video has not passed adjudication.

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
shared GPU lock before submitting to video. It uses the v2 skill, nested API
schemas, and at most one corrective generation on a concrete validation error.
Keep weights and output stores outside the checkout.

```sh
.venv/bin/python -B storygen.py write examples/market/brief.json \
  --models "$MODEL_DIR" --runtime "$LLAMA_SERVER" --out "$RUN/market-story"
.venv/bin/python -B storygen.py run examples/market/brief.json \
  --models "$MODEL_DIR" --runtime "$LLAMA_SERVER" --video-url http://127.0.0.1:8893 \
  --out "$RUN/market-video"
```

The staged renderer pair must support `GET /v2/submissions/{key}`. A resumed
directory recovers by GET instead of repeating a submitted render. Case notes,
failure diagnostics, the story, job ID, manifest and returned media hash are
retained. `sweep.py` uses the independent expectations in
`benchmark/first20.tsv`; only the brief fields are given to the writer.
