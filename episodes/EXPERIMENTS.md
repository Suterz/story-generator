# Long-form experiments

## Evidence and techniques

The [educational Reels abstract](https://proudpen.com/proceedings/index.php/mcfconf/article/download/1654/1774/6205) and [single-account preprint](https://doi.org/10.5281/zenodo.22730139) are observational. They inform the account promise and separate measures of reach, watch time, sends, saves, and follows, not a popularity score. [Brame](https://doi.org/10.1187/cbe.16-03-0125) supports signaling and removing competing detail; [Guo et al.](https://doi.org/10.1145/2556325.2566239) measured MOOC engagement proxies, not learning on Instagram. Target cuts, beat rates and narration rates are production hypotheses.

| Technique | Pinned reading | Implementation and comparison |
| --- | --- | --- |
| Persistent entities | [Shuohao novel-art and novel-storyboard, `8af10e0e`](https://github.com/eternityspring/shuohao-skills/tree/8af10e0ea1a550e4575666884f4deef780bf38ff/skills), Apache-2.0 | Use the same pair of mirrors and event IDs in both frames. `entities` on clock and bank; compare to baseline. |
| Chapter purpose and payoff | [Screenwriting Skills scene craft, `81110874`](https://github.com/jtydhr88/screenwriting-skills/tree/81110874ee98d4415f86efb8310e06b0e778e2d9/plugins/screenwriting/skills/sw-scene-craft), MIT | Resolve one viewer question and motivate the next; compare `purpose` on clock and citation. |
| Event continuity | [Story Skills plot-structure and revision-continuity, `929d6a59`](https://github.com/danjdewhurst/story-skills/tree/929d6a598de2d9ca9ae30bf85051b78a31d0a81b/skills), MIT | Generate every bank graphic from one signed event ledger. Compare `continuity` on the bank and moving-mirror briefs. |
| Visual-first planning | [AbsolutelySkilled video-scriptwriting, `2f131621`](https://github.com/AbsolutelySkilled/AbsolutelySkilled/blob/2f13162194ef2896ee497d398fd9354e8ebe2ca6/skills/video-scriptwriting/SKILL.md), MIT | Make the visual state inspectable before writing a transition or an exact spoken cue. Compare `visual-first` on bank and citation; let the aligner find measured timestamps. |
| Source verification | [Walters & Wilder, Table 3 and Results](https://doi.org/10.1038/s41598-023-41032-5); [registry-directed revision reference](https://github.com/zenstory-ai/oh-story-dsh/blob/02bb238107a86325eaa999aa3aae6fcb26a0acc9/packages/knowledge/video-recap/skills/video-script/SKILL.md), upstream MIT | Use original instructions for comparing the exact population. A relevant wrong passage is the negative. Compare `verification` on citation and bank. |

The first compact arms conflate skill with common defects (truncated prose, spoken stage markers), so none establishes a quality improvement. The combined `routed` configuration is provisional and its flags are recorded with each first draft. No external prompt files are executed or vendored. Content Skills (`1c6e909c`, MIT), Social Media Skills (`f28cef2b`, MIT) and GTM Agents (`78e0419f`, Apache-2.0) were consulted in planning; their generic hooks and format suggestions are not treated as a second independent intervention.

## Evidence folders

- `r4-review`: all six prior exports independently failed; their original acknowledgments are immutable.
- `compare` and `compare-review`: four writers × three identical decisive chapter briefs, blind narration and graphics feasibility.
- `skills` and `skill-review`: one added technique per arm with comparison cases, blinded before reading the arm identifiers.
- `candidate-01`: one release candidate freeze, separate from development and from the old sealed corpus. Advance to transfers only with three positively adjudicated MP4 hashes tied to the freeze.
- XPS: `Long Form - 10 Episodes/Chapter previews/` and `Evidence/`. The separate `Watch first/` is reserved for qualified episodes.
