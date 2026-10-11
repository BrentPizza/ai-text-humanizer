# External Detector Feedback Log

Ground truth beats the local proxy. Every time the user runs the text through a real detector and shares the report, ingest it (`scripts/gptzero_ingest.py`), run `score.py --labels` against it, and add an entry here. Patterns and weights in `score.py` and `patterns.md` should only change in response to entries in this log.

## How to read a GPTZero PDF report

- Header: `Version <model-version>`, then `AI Probability NN%`. That number is the probability the **document** is AI-written, not the share of AI sentences. Treat it as the pass/fail number.
- Sentence highlights: orange fill (~RGB 244,191,79) = high AI impact; green fill (~RGB 80,202,143) = high human impact; no fill = not scored.
- Free reports truncate the highlighted text. Sentences past the cutoff are UNSCORED, not human. `gptzero_ingest.py` reports coverage.
- Highlight boundaries follow rendered lines, so a sentence that starts mid-line can pick up a neighbour's colour. The ingest script labels each sentence by majority vote of its words.
- Labels come in contiguous runs. GPTZero appears to score in windows and smooth across neighbours, so one human-sounding sentence inside an AI-flagged paragraph usually stays orange. Fix paragraphs, not sentences.

## Runs

### 2026-10-04 · Humanizer_Test.docx · GPTZero 2026-09-13-base

- Text: free-range parenting / early childhood APA student paper, 1,852 words, already processed by this skill (no dashes, no vocabulary markers, one tell class).
- **GPTZero: 100% AI.** 59 sentences AI, 11 HUMAN, 8 UNSCORED (report truncated in the synthesis section; coverage 92%).
- **Local scorer (heuristic mode, original catalog): 25.9, PASS.** Tells sub-score 2.9: the only detected tell was M6 triad (10).
- Diagnosis: the catalog had been satisfied, so the loop stopped at iteration 1 with a false pass. The flagged text was clean of classic tells but uniformly expository: theory walk-throughs, enumerated debates, both-sides resolutions, clause chains, and a staged reflection section.
- Changes made:
  1. Added S6, S7, S3b, M26–M32 to `patterns.md` and S6, S7, S3b, M26–M31 to `score.py`.
  2. Fixed a sentence-splitter bug: the abbreviation guards never matched (`et al.` split every narrative citation into a 2-word fragment, which also fired false S2 closers and skewed length burstiness).
  3. Heuristic mode can no longer certify a pass (see SKILL.md, external gate).
- Local score after recalibration on the same text: 70.2 (FAIL). Sentence-level AUC vs GPTZero labels: 0.73, measured on the same report the new patterns were derived from, so it is optimistic. Tells fired on only ~20 of 59 AI-labelled sentences; the rest were flagged for predictability the regex catalog cannot see, which is why M32 is a paragraph-level rewrite rule rather than a detector.
- HUMAN-labelled sentences: concrete specifics (state, year, n = 422), plainly stated authorial stance, a fronted reason clause, one register-lowering word.

### 2026-10-11 · Cost Trial.docx · ZeroGPT (free web), 7 local iterations

- Text: 414-word managerial accounting paper (job order vs process costing at a restaurant), apparently earlier output of this skill. Choppy: 39 sentences, mean 10.6 words, 56% under 10 words, consequence words stripped, 2 to 4 sentence paragraphs.
- New user requirements: local combined score ≤ 15 **and** ZeroGPT < 40; the scorer must also judge writing quality; paragraphs 5 to 8 sentences. User note: ZeroGPT ~35% texts have scored 100% on GPTZero.

| Text | Old heuristic AI | New combined (AI / quality) | ZeroGPT |
|---|---|---|---|
| Original (staccato) | 28.0 PASS | 59.9 (55.1 / 68.8) gate FAIL | 39.0 |
| Iter 1 fluent, polished (6 short paras) | 49.2 | 38.6 | 71.2 (out-of-sample check) |
| Iter 2 fluent, polished, 4 paras | 46.0 | 32.5 | 66.8 (out-of-sample check) |
| Iter 5 polished, punchy, varied length | 16.9 | 29.5 | 84.6 |
| Iter 6 plain student voice | 56.2 | 14.3 | 18.6 |
| Iter 7 plain voice, tells cut (delivered) | n/a | 9.5 (13.0 / 3.0) | 21.2 |

- Diagnosis 1: the old heuristic **rewarded fragmentation**. Sentence-length CV is a poor burstiness proxy once mean length collapses, and the cadence rule had no floor.
- Diagnosis 2: on fluent text, length CV and paragraph uniformity ran **opposite** to ZeroGPT (iter 5 best on both, worst on ZeroGPT). What separated pass from fail was register: function-word share 0.35 → 0.47, average word length 5.1 → 4.5, author present in 4% → 22% of sentences. Sentence-level features did not separate ZeroGPT labels (AUC ~0.5); ZeroGPT judges windows, not sentences.
- Changes made:
  1. `score.py`: writing-quality module (fluency, short share/runs, overlong, connectives, openers, elliptic fragments, Flesch, paragraph size) with a hard gate; `combined_score = 0.65 AI + 0.35 quality`; default threshold 15.
  2. `score.py` heuristic AI: new `register` signal (0.45); tells 0.40; length CV 0.10; paragraph uniformity 0.05, now mean-length CV only (sentence-count CV dropped because it fought the 5 to 8 sentence rule).
  3. `patterns.md` S8 (staccato) and S9 (polished register); `rewriter.md` fluency floor, paragraph size, register; `qaqc.md` and `SKILL.md` dual gate with ZeroGPT.
- Caveats: register bands were fitted on 3 ZeroGPT runs and checked on 2 more (both predicted fails, both failed). Not yet checked against GPTZero; the next GPTZero report should be logged here with `score.py --labels`.
