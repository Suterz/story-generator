# Story generator

## Current baseline

- `write`, `render`, and `run` propose and submit a renderer-compatible lesson with bounded retries and a durable receipt. Use native preflight as shown in the [README](README.md).
- Independent review found defects in all 14 returns from the best saved 20-brief export run. B16 says a left notch goes to the right after a clockwise quarter-turn; it should go to the top.
- Integration handoff: frames `050f93235e3ca0db4930304cdd20ffa5584aa1b7`; video `19673754d668446e14a8f21cc3d2d16ce0fc9d1b`. See the corresponding renderer `agent-context.md` files and gallery `v4/v4.6 - Trunk integration/` for the tested triple and scope.
- Next: branch from `main`; test B16 and a different rotation lesson, and inspect the actual picture. Keep production independently pinned to V2. No reliable unattended writer or 20/20 claim.

## Decisions, newest first

- **Integration:** honor opt-in paper diagrams rather than duplicate the same evidence with generated art and overlays. The three-to-four bead reveal on bare paper retains the same first three objects. CLI supports native preflight; tests cover exact values, visible facts, and GET-only recovery. Compare upgrades with `main`, and bring genuine quality tradeoffs to the owner.
- **Phone clarity and speech:** renderer fonts caught colliding market price labels (`0d4e34f`). Explicit spoken dollars/cents preserved `$1.60`, as well as independent small-change amounts, without weakening alignment. Gallery: `v4/v4.5 - Saved rounds and rehearsal/WRITER.md`.
- **Editorial arithmetic:** separate the checklist from narration and compute exact rate/time comparisons; reject a blanket winner across opposing criteria. Bus/market exposed reversed and misleading prose despite otherwise valid requests.
- **Visual evidence:** compile exact counter rows and named visible prediction facts; a promised graphic or detached answer label cannot establish a count/relationship. Native preflight validates runtime model constraints and phone label boxes; it does not certify semantics.
- **Structured authoring:** correct the llama.cpp schema envelope, keep full validation, and bind explicitly authored utterance starts and scene parents. The first 20-brief Qwen run exported none; later candidates exported 8 (Qwen/Ryan) and 14 (Mistral Small/Heart with native preflight), with different writer configurations. These are experimental refs, not a controlled quality win.
- **Local candidates:** Qwen, Mistral Nemo, DeepSeek and Mistral Small are checksum-pinned; use one GPU lease and release it before render. Judge results independently of model reputation, JSON validity, and API status. No sealed brief corpus has been opened.
