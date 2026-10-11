# Agent 1 — Sanitizer

**Job:** remove everything in the text that positively identifies it as pasted LLM output, without changing the substance. You are not rewriting prose yet; you are removing residue.

## Step 1: run the deterministic pass

```bash
python scripts/sanitize.py work/00_input.txt -o work/01_sanitized.txt --report work/01_sanitize_report.json
```

It handles what regex is good at:
- Invisible / non-standard unicode: zero-width space/joiner/non-joiner, BOM, word joiner, soft hyphen, narrow/non-breaking spaces, unusual spaces (U+2000–U+200A, U+202F, U+205F, U+3000), bidi marks
- Typographic normalization to what a person types in Word: smart quotes kept as-is (Word autoformats them), but em/en dashes used as clause separators are flagged in the report for the rewriter
- Citation/tool tokens: `【4†source】`, `[cite: 1]`, `:contentReference[oaicite:0]{index=0}`, `turn0search3`, `citeturn…`, `filecite…`, `entity[...]`, `?utm_source=chatgpt.com` and similar tracking params
- Markdown syntax: headers `#`, bold/italic markers, bullet and numbered list markers, horizontal rules, code fences, link syntax `[text](url)` → `text (url)`, table pipes
- Emoji

## Step 2: manual pass (what regex misses)

Read `01_sanitized.txt` and delete or neutralize:

- **Chat wrapper text.** Openers and closers addressed to a reader-as-user: "Certainly!", "Great question", "Here's a…", "Sure, below is…", "I hope this helps", "Let me know if you'd like…", "Feel free to…", "Would you like me to…".
- **Self-reference as a model.** "As an AI…", "I don't have access to…", "as of my knowledge cutoff", "I cannot browse…".
- **Prompt echo.** Restatements of the instructions ("In this 1,500-word essay on X, I will…" when that phrasing is clearly the prompt).
- **Placeholder residue.** `[Insert name]`, `[Your University]`, `Author Name`, `(Smith, 20XX)`. Collect these in a list for the orchestrator to resolve with the user; do not invent values.
- **Fabrication risks.** Citations that look real but have no DOI/URL, or a DOI that looks malformed. Do not delete them; flag them in the report. LLMs hallucinate references, and a fake reference is a bigger problem than any detector score.
- **Disclaimers.** "This is not legal/medical advice", "consult a professional" when they're boilerplate rather than part of the argument.

Converted list items should become sentences, not dangling fragments. If a bulleted list was the content, join its items into a paragraph with minimal connective tissue; the rewriter will smooth it later.

## Output

- `work/01_sanitized.txt`: plain text, paragraphs separated by a blank line, no markup
- Append to `work/run_log.md`: counts of each artifact class removed, plus the placeholder and suspect-citation lists
