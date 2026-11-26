# Communication iteration

## 2026-11-26 — Generic brief contract and comparison baseline

- `b2d6053`: pin 60/20/20 communication briefs. The first 20 include six converted educational briefs; the other fourteen original lessons remain separate regressions. The sealed object is private; the public manifest stores its hash.
- `9b70394`: structured normalization preserved the supplied facts and skipped extraction. The untouched phone-policy input correctly withheld rendering. The rough model replied with `/brief/` pointers, dropped tone/audience, and misclassified a fact as verbatim. Its original result is preserved.
- The first missing-fact prompt also incorrectly withheld the sign and empathy briefs for optional details. `b2d6053` tests an explicit ready-vs-blocked decision; do not count the first refusals as a render failure or discard them.
- First four-model round uses frozen code and the unchanged tested renderer pair, Heart voice, native preflight, and the shared communication skill. Score only independently inspected communications; no default change before validation.
