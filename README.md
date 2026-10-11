# ai-text-humanizer

An agent skill that turns AI-generated or awkward writing into fluent, plain APA-7 student prose, then checks it with a local scorer and a free external detector.

**Agents: start at [`SKILL.md`](SKILL.md).** It defines the four roles (sanitizer, APA formatter, rewriter, QAQC), the rewrite loop, and the pass gates. Each role's instructions live in `agents/`; read a role's file right before running it.

## Pass gates

1. Local: `python scripts/score.py FILE` reports a combined score (0.65 × AI-likeness + 0.35 × writing quality) of 15 or less, and the writing-quality gate holds (fluent sentences, no fragment runs, body paragraphs of 5 to 8 sentences).
2. External: ZeroGPT under 40%. ZeroGPT is lenient, so a pass is necessary but not sufficient; confirm with GPTZero before submitting.

## Layout

| Path | Purpose |
|---|---|
| `SKILL.md` | Orchestration, gates, loop controls, delivery (incl. APA Word output) |
| `agents/` | Role instructions: sanitizer, apa_formatter, rewriter, qaqc |
| `references/patterns.md` | Catalog of AI-writing tells and their fixes (primary rewriter reference) |
| `references/ai_markers.md` | Overused-vocabulary list |
| `references/apa7.md` | APA 7 quick reference (page setup, title page, citations, references) |
| `references/detector_feedback.md` | Ground-truth log from real detector runs; scorer changes must trace to an entry here |
| `scripts/score.py` | Local scorer (heuristic mode needs only the standard library; full mode needs `requirements.txt`) |
| `scripts/sanitize.py` | Strips hidden unicode, tool tokens, markdown residue |
| `scripts/gptzero_ingest.py` | Parses GPTZero PDF reports into sentence labels |

## Requirements

Python 3.9+. Full scoring mode: `pip install -r scripts/requirements.txt` (torch, transformers); otherwise the scorer falls back to heuristic mode automatically.
