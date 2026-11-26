# Morning Review — repair experiments

## 2026-11-27

These experiments use frozen showcase briefs. They do not change the first-submission denominator or the 20 clips in `Watch first/`.

**Draft grammar (`c8187c3`, Mistral Small / v8 / Heart):** All three replays cleared writing preflight. The frozen attempts had been withheld for an ungrounded coordinate string (09), an ungrounded slot (03), and a pause above the supported limit (08). The replays yielded no independently verified pass.

| Slot | Replay outcome |
| --- | --- |
| 09 — Poster hierarchy | Incorrect accepted export, 27.93 s. At 9.67 s and 16.63 s the label beneath the posters changes; the posters themselves do not. The left poster omits “SATURDAY” and “OPEN STUDIO” dominates both. Captions are legible but describe stage directions and assert a hierarchy the art does not show. |
| 03 — Library return | Withheld at alignment: the recognizer bound “worryyou” where it expected “worry.” No MP4 returned. |
| 08 — Paper bird | Withheld at the first movement beat: the visual check could not confirm the bird was visible on the table. No MP4 returned. The writer used its automatic retry. |

**Opening skill (`6ca47df`, Mistral Small / Heart configuration):** GPT‑6.2 Sol recorded blind impressions before revealing the briefs and skill labels. The frozen briefs, model, seed, and runner were matched; only the skill hash differed. Review used first narration text only.

| Slot | v8 | v9 |
| --- | --- | --- |
| 02 — Quiet carriage empathy | Needs revision. “Long day?” is generic; “Here’s a quiet spot” gives an implied assurance. The script never states what the crescent identifies. | Needs revision. Removes the assurance but keeps the generic opening and still omits what the crescent identifies. |
| 16 — Seed swap welcome | Meets the narration brief. The single labeled packet is clear; “this table” depends on the illustration. | Meets the narration brief. Names the welcome table and gives the same action more concisely. |

The two text comparisons show a useful change in specificity on the invitation, but no pass gained and no evidence to change the default. The poster verdict uses decoded 360×640 frames and ASR from both the source and delivered MP4; no review included audio playback. Hash-bound evidence is in the XPS showcase `Evidence/Repair experiments/`.
