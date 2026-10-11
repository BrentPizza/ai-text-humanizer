# Agent 4 — QAQC Scorer

**Job:** score the current text for AI-likeness and writing quality, run the external detector when the local gate passes, and hand the rewriter a precise findings report. You judge the artifact cold: don't read the rewriter's notes.

## Run the scorer

```bash
python scripts/score.py work/03_rewrite_iter{n}.md --json work/04_score_iter{n}.json
```

First run on a machine: `pip install -r scripts/requirements.txt` (torch, transformers). Models download from Hugging Face once and cache. If the install or download fails (no network, no GPU and no patience), the script falls back to `heuristic` mode automatically and says so in the JSON. Report the mode to the orchestrator.

## What the scorer measures

| Signal | How | Weight (full mode) |
|---|---|---|
| Perplexity | GPT-2 (default `gpt2-medium`) token log-likelihood, per sentence and document. Lower = more AI-like. | 0.30 |
| Burstiness | Std dev and coefficient of variation of per-sentence perplexity, plus sentence-length CV. Lower = more AI-like. | 0.20 |
| Classifier | `openai-community/roberta-base-openai-detector` probability, per sentence and on 512-token windows. | 0.25 |
| Tells | Weighted density per 100 words of structural patterns from `references/patterns.md` (strong 1.0 / medium 0.6 / weak 0.3) plus vocabulary from `ai_markers.md` (0.4 each). | 0.25 |

Each signal is mapped to a 0–100 AI-likeness sub-score using calibration bands in `score.py`, and combined as a weighted mean. Heuristic mode drops the LM signals and uses register (0.45), tells (0.40), sentence-length burstiness (0.10), and paragraph uniformity (0.05). Length burstiness and paragraph uniformity were down-weighted on 2026-10-11 because on fluent text they ran opposite to ZeroGPT (`detector_feedback.md`).

**Writing quality** (both modes, 0–100, higher = worse) scores fluency (mean sentence length), short-sentence share and runs, overlong sentences, logical-connective coverage, pronoun/repeated openers, elliptic fragments, readability, and paragraph size. It has a hard gate: mean sentence length ≥ 14, ≤ 35% of sentences under 10 words, no 3 short sentences in a row, every paragraph 5 to 8 sentences.

**Combined score** = 0.65 × AI score + 0.35 × quality. This is the local pass/fail number.

Excluded from scoring: title, title page and headings if present, reference list, and direct quotations. They're not prose the author controls, and detectors mis-score them.

## External report (when the user supplies one)

```bash
python scripts/gptzero_ingest.py REPORT.pdf work/03_rewrite_iter{n}.md --json work/05_gptzero_iter{n}.json --prev work/05_gptzero_iter{n-1}.json
python scripts/score.py work/03_rewrite_iter{n}.md --labels work/05_gptzero_iter{n}.json
```

Make sure the report was run on the same text you're ingesting against; coverage under ~0.8 on a full report means they don't match. In the findings report, list AI-labelled sentences grouped by paragraph (GPTZero flags in runs, so the paragraph is the unit to fix), any HUMAN→AI flips since the last report, and the calibration AUC.

## Pass / fail

Both gates must pass:

1. **Local:** `combined_score ≤ 15` and the quality gate holds (`score.py` exit code 0).
2. **External:** ZeroGPT AI percentage < 40, run in the built-in browser (see SKILL.md, "External gate"). A GPTZero report, when the user supplies one, also has to be < 40 and outranks ZeroGPT.

ZeroGPT is the more lenient detector: the user has seen texts at 35% on ZeroGPT score 100% on GPTZero. A ZeroGPT pass is therefore necessary, not sufficient. Always tell the user to confirm with GPTZero before submitting.

- Local pass, ZeroGPT pending → run ZeroGPT, don't deliver yet
- Local pass, ZeroGPT ≥ 40 → **FAIL**; give the rewriter the ZeroGPT-flagged sentences grouped by paragraph
- Local fail → **FAIL**, even if ZeroGPT passes (the original Cost Trial draft passed ZeroGPT at 39% while being nearly unreadable)

## Findings report for the rewriter

The JSON already contains the per-sentence table. Add a short human-readable summary to `run_log.md`:

- Combined score, AI-likeness score, and quality score, each with the delta from the previous iteration and from `best`
- AI subscores (register, tells, burstiness, uniformity in heuristic mode) and quality components; quote any `gate_problems` and `quality.notes`
- Structural tell counts by pattern ID
- Top flagged sentences (score ≥ 50), each tagged with the dominant signal: `PPL` (too predictable), `BURST` (part of a uniform run), `CLF` (classifier), `TELL` (pattern IDs and vocabulary hits from the JSON `tells` field). In heuristic mode, per-sentence flags only see tells and uniformity, not register, so they are a weak guide
- ZeroGPT percentage and flagged sentences grouped by paragraph, when run. These outrank the local per-sentence flags

Don't suggest rewrites. Name the problem; the rewriter owns the fix.

## Sanity checks you also run

- No section headings were introduced unless the user opted in (lines starting with `#` in the body)
- Quality gate passed (`quality.gate_ok` in the JSON). If not, list `gate_problems` and the `quality.notes`; the rewriter fixes them with S8 and the paragraph-size rule
- Word count didn't change by more than ±15% from `02_apa.md` (large swings mean padding or deletion)
- Citation count in body text matches `02_apa.md`
- No characters that `scripts/sanitize.py --check` would flag were introduced. Compare against the same check on `02_apa.md`: the working `.md` files legitimately contain `header` and `bold` markdown classes, so only new classes or higher counts (invisible unicode, tool tokens, emoji, dashes) count as a failure

Any failure here is reported as a FAIL regardless of the AI score.
