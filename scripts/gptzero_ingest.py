#!/usr/bin/env python3
"""Ingest a GPTZero PDF report as ground-truth labels for the rewrite loop.

GPTZero's exported "AI Report" PDF highlights each sentence with a background
rectangle: orange (~#F4BF4F) = high AI impact, green (~#50CA8F) = high human
impact, no fill = not scored (free reports truncate the document). This script
recovers those labels, aligns them to the sentences of the current working
text, and writes a findings JSON the rewriter consumes in place of (or on top
of) the local score.py output.

Usage:
  gptzero_ingest.py REPORT.pdf TEXT.md --json OUT.json [--prev PREV.json]

Output JSON:
  detector, version, doc_ai_probability (0-100), coverage (share of TEXT words
  that appear in the report), counts {AI, HUMAN, UNSCORED}, sentences[] with
  {sentence, label, ai_share}, and, with --prev, flips[] (label changes vs the
  previous report on matched sentences).
"""
import argparse
import difflib
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from score import extract_prose, split_sentences  # noqa: E402

AI_RGB = (0.957, 0.749, 0.310)
HUMAN_RGB = (0.314, 0.792, 0.561)


def _near(c, ref, tol=0.04):
    return c is not None and len(c) == 3 and all(abs(a - b) <= tol for a, b in zip(c, ref))


def norm(w):
    return re.sub(r"[^a-z0-9]", "", w.lower().replace("’", "'"))


def read_report(pdf_path):
    import pdfplumber

    stream, header = [], ""
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            txt = page.extract_text() or ""
            header += txt + "\n"
            rects = []
            for r in page.rects:
                c = tuple(r.get("non_stroking_color") or ())
                if r["height"] < 8 or r["width"] < 3:
                    continue  # legend gradient swatches, rules
                if _near(c, AI_RGB):
                    rects.append((r, "AI"))
                elif _near(c, HUMAN_RGB):
                    rects.append((r, "HUMAN"))
            for w in page.extract_words():
                if w["top"] < 40 and "Version" in txt[:40]:
                    continue
                cx, cy = (w["x0"] + w["x1"]) / 2, (w["top"] + w["bottom"]) / 2
                lab = None
                for r, l in rects:
                    if r["x0"] <= cx <= r["x1"] and r["top"] <= cy <= r["bottom"]:
                        lab = l
                        break
                stream.append((norm(w["text"]), lab))
            if re.search(r"^FAQs\s*$", txt, re.M):
                break  # everything after is GPTZero boilerplate
    m = re.search(r"AI Probability[^\n]*\n\s*(\d{1,3})%", header) or re.search(r"AI Probability\s*(\d{1,3})%", header)
    v = re.search(r"Version\s+(\S+)", header)
    return [s for s in stream if s[0]], (int(m.group(1)) if m else None), (v.group(1) if v else None)


def align(sentences, stream):
    """Label each sentence by majority vote of the report words it matches."""
    rwords = [w for w, _ in stream]
    out, cursor = [], 0
    for s in sentences:
        sw = [norm(w) for w in s.split() if norm(w)]
        if not sw:
            continue
        # search a window ahead of the cursor; texts are in the same order
        lo, hi = max(0, cursor - 40), min(len(rwords), cursor + len(sw) * 4 + 400)
        sm = difflib.SequenceMatcher(None, sw, rwords[lo:hi], autojunk=False)
        labs, last = [], None
        for blk in sm.get_matching_blocks():
            for k in range(blk.size):
                j = lo + blk.b + k
                labs.append(stream[j][1])
                last = j
        matched = len(labs) / len(sw)
        if matched < 0.5:
            out.append({"sentence": s, "label": "UNSCORED", "ai_share": None})
            continue
        cursor = (last or cursor) + 1
        scored = [l for l in labs if l]
        if len(scored) < 0.5 * len(labs):
            out.append({"sentence": s, "label": "UNSCORED", "ai_share": None})
            continue
        ai = sum(1 for l in scored if l == "AI") / len(scored)
        out.append({"sentence": s, "label": "AI" if ai >= 0.5 else "HUMAN", "ai_share": round(ai, 2)})
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("report")
    ap.add_argument("text")
    ap.add_argument("--json", required=True)
    ap.add_argument("--prev", help="previous gptzero_ingest JSON, to report label flips")
    a = ap.parse_args()

    stream, prob, ver = read_report(a.report)
    paras = extract_prose(open(a.text, encoding="utf-8").read())
    sents = [s for p in paras for s in split_sentences(p)]
    labeled = align(sents, stream)
    counts = {k: sum(1 for x in labeled if x["label"] == k) for k in ("AI", "HUMAN", "UNSCORED")}
    words = sum(len(x["sentence"].split()) for x in labeled)
    cov = sum(len(x["sentence"].split()) for x in labeled if x["label"] != "UNSCORED") / max(words, 1)
    res = {
        "detector": "gptzero",
        "version": ver,
        "doc_ai_probability": prob,
        "coverage": round(cov, 2),
        "counts": counts,
        "sentences": labeled,
    }
    if a.prev:
        prev = {x["sentence"]: x["label"] for x in json.load(open(a.prev))["sentences"]}
        res["flips"] = [
            {"sentence": x["sentence"], "from": prev[x["sentence"]], "to": x["label"]}
            for x in labeled if x["sentence"] in prev and prev[x["sentence"]] != x["label"]
        ]
    json.dump(res, open(a.json, "w"), indent=2)
    print(f"GPTZero {ver}: doc AI probability={prob}%  coverage={cov:.0%}  "
          f"AI={counts['AI']} HUMAN={counts['HUMAN']} UNSCORED={counts['UNSCORED']}")
    for x in labeled:
        if x["label"] == "AI":
            print(f"  [AI {x['ai_share']}] {x['sentence'][:100]}")
    if cov < 0.9:
        print(f"  note: report covers {cov:.0%} of the text; UNSCORED sentences are unknown, not human")


if __name__ == "__main__":
    main()
