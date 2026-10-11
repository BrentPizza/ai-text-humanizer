#!/usr/bin/env python3
"""Deterministic AI-artifact removal.

Usage:
  sanitize.py INPUT [-o OUTPUT] [--report REPORT.json]
  sanitize.py INPUT --check        # exit 1 if any artifact class is present
"""
import argparse
import json
import re
import sys
import unicodedata
from collections import Counter

# --- invisible / non-standard unicode ---------------------------------------
INVISIBLE = {
    "\u200b": "", "\u200c": "", "\u200d": "", "\u2060": "", "\ufeff": "",
    "\u00ad": "", "\u200e": "", "\u200f": "", "\u202a": "", "\u202b": "",
    "\u202c": "", "\u202d": "", "\u202e": "", "\u2066": "", "\u2067": "",
    "\u2068": "", "\u2069": "", "\u180e": "",
}
ODD_SPACES = re.compile(r"[\u00a0\u1680\u2000-\u200a\u202f\u205f\u3000]")

# --- LLM citation / tool tokens ---------------------------------------------
TOOL_PATTERNS = [
    ("oai_bracket_cite", re.compile(r"【[^】]{0,80}】")),
    ("content_reference", re.compile(r":?contentReference\[oaicite:\d+\]\{index=\d+\}")),
    ("oaicite", re.compile(r"\[?oaicite:\d+\]?")),
    ("turn_search", re.compile(r"\b(?:cite)?turn\d+(?:search|news|view|fetch|file)\d+\b")),
    ("cite_turn", re.compile(r"\ue200cite\ue202[^\ue201]*\ue201|citeturn\S*")),
    ("filecite", re.compile(r"\bfilecite\S*")),
    ("entity_tag", re.compile(r"\bentity\[[^\]]*\]")),
    ("cite_bracket", re.compile(r"\[cite(?:_start|_end)?(?::\s*[\d,\s]+)?\]")),
    ("source_bracket", re.compile(r"\[source:?\s*\d+\]", re.I)),
    ("private_use", re.compile(r"[\ue000-\uf8ff]")),
]
TRACKING = re.compile(r"([?&])(utm_[a-z]+|ref|source)=(chatgpt\.com|openai|claude|gemini|copilot|perplexity)[^&\s)]*&?", re.I)

# --- markdown ----------------------------------------------------------------
MD = [
    ("code_fence", re.compile(r"^```.*$", re.M), ""),
    ("hrule", re.compile(r"^\s*(?:[-*_]\s*){3,}$", re.M), ""),
    ("header", re.compile(r"^\s{0,3}#{1,6}\s+", re.M), ""),
    ("blockquote", re.compile(r"^\s*>\s?", re.M), ""),
    ("bullet", re.compile(r"^\s*[-*+•]\s+", re.M), ""),
    ("numbered", re.compile(r"^\s*\d+[.)]\s+", re.M), ""),
    ("table_sep", re.compile(r"^\s*\|?\s*:?-{2,}:?\s*(\|\s*:?-{2,}:?\s*)+\|?\s*$", re.M), ""),
    ("image", re.compile(r"!\[([^\]]*)\]\([^)]*\)"), r"\1"),
    ("link", re.compile(r"\[([^\]]+)\]\((https?://[^)\s]+)\)"), r"\1 (\2)"),
    ("bold", re.compile(r"(\*\*|__)(?=\S)(.+?)(?<=\S)\1"), r"\2"),
    ("italic", re.compile(r"(?<![*\w])([*_])(?=\S)(.+?)(?<=\S)\1(?![*\w])"), r"\2"),
    ("inline_code", re.compile(r"`([^`]+)`"), r"\1"),
]

EMOJI = re.compile(
    "[\U0001F300-\U0001FAFF\U00002600-\U000027BF\U0001F000-\U0001F2FF\U0001F900-\U0001F9FF\ufe0f]"
)

CHAT_RESIDUE = re.compile(
    r"^(?:certainly|sure|absolutely|of course|great question|here(?:'s| is| are))\b[^\n]*?[!:.]\s*$"
    r"|^(?:i hope this helps|let me know if|feel free to|would you like me to|if you(?:'d| would) like)[^\n]*$",
    re.I | re.M,
)
SELF_REF = re.compile(r"\bas an ai(?: language model)?\b|\bmy (?:knowledge|training) cutoff\b", re.I)
EM_DASH = re.compile(r"\s?[—–]\s?")


def table_rows_to_text(text, counts):
    out = []
    for line in text.split("\n"):
        if re.match(r"^\s*\|.*\|\s*$", line):
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            out.append("; ".join(c for c in cells if c))
            counts["table_row"] += 1
        else:
            out.append(line)
    return "\n".join(out)


def sanitize(text):
    counts = Counter()
    flags = {}

    text = unicodedata.normalize("NFC", text)
    for ch, rep in INVISIBLE.items():
        n = text.count(ch)
        if n:
            counts["invisible_char"] += n
            text = text.replace(ch, rep)
    text, n = ODD_SPACES.subn(" ", text)
    counts["odd_space"] += n

    for name, pat in TOOL_PATTERNS:
        text, n = pat.subn("", text)
        counts[name] += n
    text, n = TRACKING.subn(lambda m: m.group(1) if m.group(0).endswith("&") else "", text)
    counts["tracking_param"] += n
    text = re.sub(r"[?&]\)", ")", text)

    text = table_rows_to_text(text, counts)
    for name, pat, rep in MD:
        text, n = pat.subn(rep, text)
        counts[name] += n

    text, n = EMOJI.subn("", text)
    counts["emoji"] += n

    residue = [m.group(0).strip() for m in CHAT_RESIDUE.finditer(text)]
    text, n = CHAT_RESIDUE.subn("", text)
    counts["chat_residue_line"] += n
    if residue:
        flags["chat_residue_removed"] = residue

    self_ref = [m.group(0) for m in SELF_REF.finditer(text)]
    if self_ref:
        flags["self_reference_needs_manual_review"] = self_ref

    flags["em_dash_count"] = len(EM_DASH.findall(text))
    flags["placeholders"] = sorted(set(re.findall(r"\[(?:insert|your|author|name|date|citation)[^\]]*\]|\b20XX\b", text, re.I)))

    # tidy whitespace
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r" +([.,;:!?])", r"\1", text)
    text = re.sub(r"\n[ \t]+", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text).strip() + "\n"

    return text, {k: v for k, v in counts.items() if v}, flags


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("input")
    ap.add_argument("-o", "--output")
    ap.add_argument("--report")
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args()

    raw = open(a.input, encoding="utf-8").read()
    clean, counts, flags = sanitize(raw)

    if a.check:
        hard = {k: v for k, v in counts.items() if k not in ("odd_space",)}
        print(json.dumps(hard, indent=2))
        sys.exit(1 if hard else 0)

    if a.output:
        open(a.output, "w", encoding="utf-8").write(clean)
    else:
        sys.stdout.write(clean)
    report = {"removed": counts, "flags": flags}
    if a.report:
        json.dump(report, open(a.report, "w"), indent=2)
    print(json.dumps(report, indent=2), file=sys.stderr)


if __name__ == "__main__":
    main()
