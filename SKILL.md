---
name: "ai-text-humanizer"
description: Multi-agent pipeline that takes AI-generated or awkward writing, strips AI artifacts (chat residue, citation tokens, hidden unicode, markdown), reformats it into APA 7th edition, and rewrites it into fluent, plain student prose that does not read as LLM output, using a catalog of structural AI tells (not-X-but-Y, closers, triads, dashes, -ing riders, inflation, polished register) and a fluency floor that blocks choppy over-correction. Scores every draft locally for AI-likeness plus writing quality (fluency, sentence structure, 5-8 sentence paragraphs) and loops until the combined local score is at or below 15 and a free ZeroGPT scan is under 40%. Ingests GPTZero PDF reports as ground truth. Delivers APA-7 Word documents, with a title page when asked. Use whenever the user wants text humanized, de-AI'd, passed through AI detection, made more fluid, converted to APA-7, or scored for AI likelihood, or when they upload a GPTZero report to drive the next rewrite, even if they only say "clean this up so it doesn't read like AI" or "make this APA and human-sounding".
---

# AI Text Humanizer (APA-7)

Four roles, run in a fixed order, with two gates and a rewrite loop:

```
input ──► [1 SANITIZER] ──► [2 APA FORMATTER] ──► [3 REWRITER] ──► [4 QAQC] ──► local ≤ 15 AND ZeroGPT < 40? ──► deliver
                                                       ▲                                    │ no
                                                       └───────────── findings report ──────┘
```

Each role has its own instruction file in `agents/`. Read a role's file right before running that role, not all at once.

| Role | File | Deterministic helper |
|---|---|---|
| 1 Sanitizer | `agents/sanitizer.md` | `scripts/sanitize.py` |
| 2 APA formatter | `agents/apa_formatter.md` | reference: `references/apa7.md` |
| 3 Rewriter | `agents/rewriter.md` | references: `references/patterns.md` (primary), `references/ai_markers.md` |
| 4 QAQC scorer | `agents/qaqc.md` | `scripts/score.py`, `scripts/gptzero_ingest.py`, reference: `references/detector_feedback.md` |

## Running the agents

**With subagents (Claude Code, Cowork):** spawn each role as its own subagent and pass only the role file, the current text file, and (for the rewriter) the latest QAQC report and external flags. Isolation matters most for QAQC: the scorer should not see the rewriter's reasoning, only the text, so it judges the artifact cold.

**Without subagents (claude.ai):** run the roles yourself, sequentially. Before each role, re-read its file and adopt only that role's job. Do not let the rewriter "pre-grade" its own work; scores come from `scripts/score.py` and the external detector, never from your own estimate.

## Workspace

Keep every stage on disk so the loop is auditable and reversible:

```
work/
  00_input.txt
  01_sanitized.txt
  02_apa.md                 # APA structure, pre-rewrite
  03_rewrite_iter{n}.md
  04_score_iter{n}.json     # score.py output
  05_zerogpt_iter{n}.json   # {"pct": .., "flagged": [sentences]}
  05_gptzero_iter{n}.json   # ingested GPTZero report, when the user supplies one
  final.md / final.docx
  run_log.md                # one line per stage: stage, iteration, scores, notes
```

## The gates

Both must pass (the user can override either threshold):

1. **Local:** `combined_score ≤ 15` and the writing-quality gate holds (`score.py` exits 0). Combined = 0.65 × AI-likeness + 0.35 × writing quality; see `agents/qaqc.md`.
2. **External:** ZeroGPT AI percentage < 40, run in the built-in browser (see "External detectors").

Neither gate is enough alone. A choppy, unreadable draft passed ZeroGPT at 39%, and a polished draft that passed the old local scorer got 84.6% on ZeroGPT (`references/detector_feedback.md`). ZeroGPT is also more lenient than GPTZero: texts at ~35% on ZeroGPT have scored 100% on GPTZero. Always tell the user to confirm with GPTZero before submitting.

## The loop

1. Save input to `work/00_input.txt`.
2. **Sanitizer** → `01_sanitized.txt`.
3. **APA formatter** → `02_apa.md`. Default layout: title, continuous body paragraphs of 5 to 8 sentences, references. No title page and no section headings unless the user asks. Strip headings from the input if present and log them.
4. Set `iter = 1`. If the user supplied a writing sample, save it as `work/voice_sample.txt` and pass it to the rewriter every iteration.
5. **Rewriter** on the latest text (+ last QAQC JSON and last external flags if `iter > 1`) → `03_rewrite_iter{n}.md`.
6. **QAQC, local:** `python scripts/score.py work/03_rewrite_iter{n}.md --json work/04_score_iter{n}.json`. If it fails, go to step 8.
7. **QAQC, external:** run ZeroGPT on the body text, save `05_zerogpt_iter{n}.json`, and add the result to the calibration table in `detector_feedback.md`. If both gates pass, go to step 9.
8. Apply the loop controls, then `iter += 1` and return to step 5.
9. **Final integrity pass** (orchestrator, not the rewriter): every in-text citation has a matching reference entry and vice versa; no factual claim, number, quotation, or citation changed meaning between `02_apa.md` and the final text; any illustrative example the rewriter added is clearly hypothetical or a direct consequence of a stated fact; APA formatting survived. Fix drift directly.
10. **Deliver.** Write `final.md`. For Word, read the docx skill and build `final.docx` per `references/apa7.md`: US Letter, 1" margins, Times New Roman 12 (or another APA font), double spacing throughout with no extra paragraph spacing, 0.5" first-line indent, page number top right on every page. Student title page when the user asks for one (layout in `agents/apa_formatter.md`), then the bold centered title on the first text page, body, and References on a new page only if sources are cited. No headings unless the user opted in. Render the .docx to PDF and look at every page before handing it over. On Windows the docx skill's `soffice.py` fails (no AF_UNIX sockets); export through Word instead (PowerShell: `Word.Application` COM, `Documents.Open`, `ExportAsFixedFormat(path, 17)`) and read the PDF directly.

### Loop controls

Every pass is another chance for meaning to drift, so the loop has three circuit breakers.

- **Regression guard.** Rank iterations by ZeroGPT among those that pass the local gate (by combined score if none has reached ZeroGPT yet); that one is `best`. If an iteration is worse than `best`, the next one starts from `best`, and the rewriter is told which edits made it worse (diff the two files).
- **Strategy escalation.** If 2 consecutive iterations each improve by less than 2 points, sentence-level edits have stalled. The next iteration works at paragraph level: re-sequence claims, merge paragraphs, change paragraph openings, shift register (S9), all within the frozen-zone rules.
- **Hard stop.** Stop at 8 iterations, or after a paragraph-level iteration also fails to improve by 2 points. Deliver `best`, not the last iteration, and escalate to the user (see "Report back").

## External detectors

### ZeroGPT (every iteration that passes locally)

Ask the user once per session before pasting their text into ZeroGPT, because it sends the paper to a third-party site. Then, in the built-in browser:

1. Open `https://www.zerogpt.com/`, decline non-essential cookies, and put the **body text only** (no title page, title, or references) in the textarea.
2. Click **Detect Text** and read the "NN% AI GPT" figure. Highlighted spans (`span[style*="background"]`) are the flagged sentences.
3. ZeroGPT flags in paragraph-sized windows, and its per-sentence flags move between runs, so the rewriter treats a flagged paragraph as the unit.
4. The free limit is 15,000 characters per scan; split longer papers at paragraph boundaries and report a word-weighted mean.

### GPTZero (when the user uploads a report)

GPTZero's free scan redirects to an app that requires an account. Claude cannot create accounts, so the user runs it and uploads the PDF report.

1. `python scripts/gptzero_ingest.py REPORT.pdf work/<text the report was run on> --json work/05_gptzero_iter{n}.json [--prev work/05_gptzero_iter{n-1}.json]`
2. The report's document **AI Probability** must also be < 40, and it outranks ZeroGPT for that iteration. Its number is bimodal, so expect large jumps rather than gradual descent.
3. The rewriter gets the ingested JSON. AI-labelled sentences are the target list; HUMAN-labelled ones are frozen by default; UNSCORED ones are unknown.
4. Calibrate: `python scripts/score.py <same text> --labels work/05_gptzero_iter{n}.json`. If AUC is below ~0.65, or a tell fires mostly on HUMAN-labelled sentences, log it in `detector_feedback.md` and adjust `score.py` or `patterns.md` before the next iteration.

Reports from any other detector go in `detector_feedback.md` too; only the GPTZero PDF format is parsed automatically.

## Guardrails on the rewrite loop

- **Meaning is fixed.** Wording and structure change; claims don't. The rewriter runs a fact audit every iteration (`agents/rewriter.md`), and the orchestrator re-checks in step 9.
- **Quotes and citations are frozen.** Direct quotations, citation strings, DOIs, and reference entries are never touched.
- **Readable first.** Never pass a gate by making the paper worse to read. The quality gate exists because an earlier version of this skill did exactly that.
- **No dashes** in the final text unless a user writing sample uses them (pattern M8). Number-range en dashes (pp. 14–22) are fine.
- **Plain student voice.** The author may appear ("I think", "In my view") and commit to judgments the content supports. No rhetorical questions, staged candor, or invented personal experiences.
- **No garbage injection.** Typos, random synonyms, homoglyphs, or invisible characters drop scores but damage the paper and are caught by `sanitize.py --check`.

## Report back to the user

Short summary after delivery:
- Final scores: combined (AI-likeness and quality separately), ZeroGPT, and GPTZero if a report was supplied; the per-iteration history
- Which signals and catalog patterns drove the changes
- Any additions the user should check: hypothetical examples, first-person hedges, softened claims
- Any sentences that stayed flagged and why they were left alone
- **If the hard stop hit:** the best scores reached, residual flags grouped by cause (frozen zone, genre-standard phrasing, would change the claim), and the two options most likely to help: a sample of the user's own writing for voice matching, or permission to restructure specific sections
- Scorer mode (`full` with local LMs, or `heuristic`). Heuristic mode's AI-likeness half is calibrated on a handful of ZeroGPT runs, so treat it as a prescreen

Be straight about what the scores are. The local scorer is a heuristic proxy plus a writing-quality check. ZeroGPT is lenient. Only a GPTZero scan the user runs says anything about GPTZero.
