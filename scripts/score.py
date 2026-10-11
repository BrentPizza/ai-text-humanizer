#!/usr/bin/env python3
"""GPTZero-style AI-likelihood scorer.

Signals (full mode):
  perplexity   GPT-2 token NLL per sentence and document          w=0.30
  burstiness   CV of sentence perplexity + sentence-length CV     w=0.20
  classifier   roberta-base-openai-detector P(AI)                  w=0.25
  tells        weighted structural + vocab tell density (patterns.md) w=0.25
Heuristic mode (no torch/transformers or model download fails):
  register 0.45, tells 0.40, length burstiness 0.10, paragraph uniformity 0.05
Writing quality (both modes, 0-100, higher = worse writing):
  fluency, short-sentence share/runs, overlong sentences, logical connectives,
  repeated/pronoun openers, elliptic fragments, readability, paragraph size.
  Hard gate on staccato prose and on paragraphs outside 5-8 sentences.
Combined score = 0.65 * AI score + 0.35 * quality score.  PASS = combined <= threshold
  AND the quality gate holds.

Usage:
  score.py FILE [--json OUT.json] [--threshold 15] [--mode auto|full|heuristic]
               [--lm gpt2-medium] [--clf openai-community/roberta-base-openai-detector]
"""
import argparse
import json
import math
import os
import re
import statistics as st
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
MARKERS_FILE = os.path.join(HERE, "..", "references", "ai_markers.md")


# ---------------------------------------------------------------- text prep --
def load_markers():
    try:
        raw = open(MARKERS_FILE, encoding="utf-8").read()
        block = raw.split("<!-- BEGIN MARKERS -->")[1].split("<!-- END MARKERS -->")[0]
        return [l.strip().lower() for l in block.splitlines() if l.strip() and not l.strip().startswith("#")]
    except Exception:
        return []


def extract_prose(text):
    """Drop title page, headings, reference list, block quotes, and direct quotes."""
    # only drop a leading title page when one is marked; the default layout has none,
    # and splitting on the first page break would otherwise discard the whole body
    if text.lstrip().startswith("<!-- TITLE PAGE -->") and "<!-- PAGE BREAK -->" in text:
        text = text.split("<!-- PAGE BREAK -->", 1)[1]
    text = re.split(r"(?im)^\s*\**\s*references\s*\**\s*$", text)[0]
    keep = []
    for para in re.split(r"\n\s*\n", text):
        p = para.strip()
        if not p or p.startswith("<!--"):
            continue
        if re.match(r"^#{1,3}\s", p) or re.fullmatch(r"\*\*[^*]+\*\*", p):
            continue  # level 1-3 heading or bold title line
        p = re.sub(r"^#{4,5}\s+[^.]+\.\s*", "", p)  # run-in level 4/5 heading
        if p.startswith(">"):
            continue
        p = re.sub(r"[\"“][^\"”]{25,}[\"”]", " ", p)  # direct quotes (~5+ words)
        p = re.sub(r"\*\*|__|(?<!\w)[*_](?!\s)|(?<!\s)[*_](?!\w)", "", p)
        keep.append(re.sub(r"\s+", " ", p).strip())
    return [p for p in keep if p]


# lookbehinds sit after the period, so each abbreviation includes its own final "."
ABBR = r"(?<!\bet al\.)(?<!\be\.g\.)(?<!\bi\.e\.)(?<!\bp\.)(?<!\bpp\.)(?<!\bvs\.)(?<!\bDr\.)(?<!\bMr\.)(?<!\bMs\.)(?<!\bNo\.)(?<!\bn\.d\.)"


def split_sentences(para):
    parts = re.split(ABBR + r"(?<=[.!?])[\"”')\]]*\s+(?=[A-Z(\"“])", para)
    return [s.strip() for s in parts if len(s.split()) >= 3]


FLUENCY_MIN_MEAN = 14          # human academic prose typically averages 17-25 words/sentence
FLUENCY_MAX_SHORT_SHARE = 0.35
FLUENCY_MAX_SHORT_RUN = 3      # three sub-10-word sentences in a row reads as staccato
PARA_MIN_SENTS, PARA_MAX_SENTS = 5, 8   # user convention: few, full paragraphs
AI_WEIGHT, QUALITY_WEIGHT = 0.65, 0.35

# words that carry reasoning between clauses; without them prose reads as a list of facts
CONNECTIVES = re.compile(
    r"\b(?:because|since|although|though|while|whereas|so|therefore|thus|hence|unless|if|when|whenever|"
    r"after|before|until|once|which|whose|where|but|yet|however|instead|rather than|by contrast|"
    r"as a result|so that|in order to|meaning)\b", re.I)
PRONOUN_OPENER = re.compile(r"^(?:They|It|These|Those|This|That|He|She|We|Its|Their)\b")
# bare fragments that lean entirely on the previous sentence ("Takeout packaging does too.")
ELLIPTIC = re.compile(r"\b(?:does|do|did|is|are|was|were) (?:too|also|as well)\.$", re.I)


def clamp(x, lo=0.0, hi=100.0):
    return max(lo, min(hi, x))


def band(x, ai_end, human_end, log=False):
    """Map x to 0-100 AI-likeness: x<=ai_end ->100, x>=human_end ->0 (or reversed)."""
    if log:
        x, ai_end, human_end = (math.log(max(v, 1e-6)) for v in (x, ai_end, human_end))
    if ai_end == human_end:
        return 50.0
    return clamp(100.0 * (human_end - x) / (human_end - ai_end))


def cv(vals):
    vals = [v for v in vals if v is not None]
    if len(vals) < 2:
        return 0.0
    m = st.mean(vals)
    return st.pstdev(vals) / m if m else 0.0


def syllables(word):
    w = re.sub(r"[^a-z]", "", word.lower())
    if not w:
        return 0
    groups = re.findall(r"[aeiouy]+", w)
    n = len(groups) - (1 if w.endswith("e") and not w.endswith(("le", "ee")) and len(groups) > 1 else 0)
    return max(1, n)


FUNCTION_WORDS = set("""a an the of to in on at for with by from as is are was were be been being it its this
that these those and or but so if then than because although though while when which who whom whose what there here
i you we they he she me my your our their them us not no can could would should will may might do does did have has had
just also very really up out over about into more most some any all each other such only how""".split())
AUTHOR = re.compile(r"\b(?:I|my|me|you|your|we|our)\b")


def register(sents):
    """Plain-voice register, 0-100 AI-likeness. Polished, noun-heavy prose (few function words, long words,
    no author present) is what ZeroGPT flagged in fluent text; plain explanatory student prose passed.
    Calibrated on 3 ZeroGPT runs (2026-10-11, detector_feedback.md): provisional."""
    words = [w for s in sents for w in re.findall(r"[A-Za-z'-]+", s)]
    fw = sum(w.lower() in FUNCTION_WORDS for w in words) / max(len(words), 1)
    awl = st.mean(len(w) for w in words) if words else 0
    author = sum(bool(AUTHOR.search(s)) for s in sents) / len(sents)
    sc = 0.4 * band(fw, 0.34, 0.46) + 0.4 * band(awl, 5.2, 4.5) + 0.2 * band(author, 0.0, 0.20)
    return sc, {"function_word_share": round(fw, 3), "avg_word_len": round(awl, 2), "author_presence": round(author, 2)}


def quality(sents, lens, para_idx):
    """Writing-quality score, 0-100 (higher = worse). Independent of AI-likeness."""
    n = len(sents)
    short = [l < 10 for l in lens]
    run = best_run = 0
    for s_ in short:
        run = run + 1 if s_ else 0
        best_run = max(best_run, run)
    mean_len = st.mean(lens)
    short_share = sum(short) / n
    long_share = sum(l > 40 for l in lens) / n
    conn_share = sum(bool(CONNECTIVES.search(s)) for s in sents) / n
    pron_share = sum(bool(PRONOUN_OPENER.match(s)) for s in sents) / n
    firsts = [s.split()[0].lower() for s in sents]
    rep_pairs = sum(1 for i in range(1, n) if firsts[i] == firsts[i - 1] and para_idx[i] == para_idx[i - 1])
    rep_share = rep_pairs / max(n - 1, 1)
    elliptic = [s for s in sents if ELLIPTIC.search(s)]
    words = [w for s in sents for w in s.split()]
    fre = 206.835 - 1.015 * (len(words) / n) - 84.6 * (sum(syllables(w) for w in words) / max(len(words), 1))
    counts = [para_idx.count(i) for i in sorted(set(para_idx))]
    bad_paras = [i + 1 for i, c in enumerate(counts) if not PARA_MIN_SENTS <= c <= PARA_MAX_SENTS]
    off = sum(max(PARA_MIN_SENTS - c, c - PARA_MAX_SENTS, 0) for c in counts) / len(counts)

    comp = {
        "fluency": max(band(mean_len, 11, 17), band(mean_len, 38, 30)),
        "short_share": band(short_share, 0.45, 0.20),
        "short_runs": 100.0 if best_run >= 3 else (30.0 if best_run == 2 else 0.0),
        "overlong": band(long_share, 0.25, 0.05),
        "connectives": band(conn_share, 0.15, 0.45),
        "openers": max(band(pron_share, 0.35, 0.10), band(rep_share, 0.30, 0.05)),
        "fragments": min(100.0, 50.0 * len(elliptic)),
        "readability": band(fre, 5, 30),
        "paragraph_size": band(off, 2.0, 0.0),
    }
    weights = {"fluency": 0.17, "short_share": 0.10, "short_runs": 0.10, "overlong": 0.07,
               "connectives": 0.15, "openers": 0.13, "fragments": 0.06, "readability": 0.07,
               "paragraph_size": 0.15}
    q = sum(comp[k] * w for k, w in weights.items())

    problems = []
    if mean_len < FLUENCY_MIN_MEAN:
        problems.append(f"mean sentence length {mean_len:.1f} < {FLUENCY_MIN_MEAN} words")
    if short_share > FLUENCY_MAX_SHORT_SHARE:
        problems.append(f"{short_share:.0%} of sentences under 10 words (max {FLUENCY_MAX_SHORT_SHARE:.0%})")
    if best_run >= FLUENCY_MAX_SHORT_RUN:
        problems.append(f"{best_run} consecutive sentences under 10 words (max {FLUENCY_MAX_SHORT_RUN - 1})")
    if bad_paras:
        problems.append(f"paragraph(s) {bad_paras} outside {PARA_MIN_SENTS}-{PARA_MAX_SENTS} sentences "
                        f"(counts {counts}); merge short ones, split long ones")
    notes = [f"elliptic fragment: {e}" for e in elliptic]
    if comp["connectives"] >= 50:
        notes.append(f"only {conn_share:.0%} of sentences carry a logical connective; facts read as a list")
    if comp["openers"] >= 50:
        notes.append(f"{pron_share:.0%} of sentences open on a bare pronoun / {rep_share:.0%} repeat the previous opener")
    if comp["overlong"] >= 50:
        notes.append(f"{long_share:.0%} of sentences over 40 words")
    return {
        "score": round(q, 1),
        "gate_ok": not problems,
        "gate_problems": problems,
        "components": {k: round(v, 1) for k, v in comp.items()},
        "metrics": {"mean_sentence_len": round(mean_len, 1), "short_share": round(short_share, 2),
                    "max_short_run": best_run, "long_share": round(long_share, 2),
                    "connective_share": round(conn_share, 2), "pronoun_opener_share": round(pron_share, 2),
                    "repeated_opener_share": round(rep_share, 2), "flesch_reading_ease": round(fre, 1),
                    "paragraph_sentence_counts": counts},
        "notes": notes,
    }


# ---------------------------------------------------------------- signals ----
def marker_hits(sentence, markers):
    s = " " + sentence.lower() + " "
    return [m for m in markers if re.search(r"(?<![a-z])" + re.escape(m) + r"(?![a-z])", s)]


TRICOLON = re.compile(r"\b\w+(?:\s\w+)?,\s\w+(?:\s\w+)?,\s(?:and|or)\s\w+", re.I)
DASH = re.compile(r"—|\s–\s|\s--\s")

# Structural tells from references/patterns.md: (id, weight, regex). strong 1.0 / medium 0.6 / weak 0.3
I = re.I
TELLS = [
    ("S1_not_x_but_y", 1.0, re.compile(r"\bnot (?:just|only|merely|simply|solely)\b[^.;]{1,80}?\bbut\b|\b(?:it|this|that)(?:'s| is) not [^.;]{1,60}[;,]\s*(?:it|this|that)(?:'s| is)\b|,\s(?:not|rather than) (?:just |merely )?[a-z]+(?: [a-z]+)?\.$", I)),
    ("S2_closer", 1.0, re.compile(r"^(?:this|that|these|such) (?:shows|demonstrates|illustrates|highlights|underscores|reinforces|reveals|is why|distinction matters|matters)\b|^the (?:message|lesson|takeaway) (?:was|is) clear|^(?:and )?that(?:'s| is) the (?:real|key|point)", I)),
    ("S3_aphorism", 1.0, re.compile(r"\b(?:the real (?:question|issue|problem|challenge)|at its core|at the heart of|what (?:really|truly) matters|the deeper issue|is the (?:language|currency|architecture|lifeblood) of)\b", I)),
    ("S4_staged_runup", 1.0, re.compile(r"^(?:let(?:'s| us) (?:dive|explore|break|look|unpack|examine|consider)|here(?:'s| is) (?:the thing|what)|the thing is|honestly[?,]|real talk|without further ado|consider the following)", I)),
    ("S5_arguing_with_no_one", 1.0, re.compile(r"^(?:this (?:isn't|is not) (?:just |mainly |merely |simply )?(?:about|to say)|i(?:'m| am) not saying|to be clear|don't get me wrong|one might be tempted|a tempting approach|it would be easy to (?:assume|think|just)|you might think)", I)),
    ("M6_triad", 0.6, re.compile(r"\b\w+(?:\s\w+)?,\s\w+(?:\s\w+)?,\s(?:and|or)\s\w+", I)),
    ("M8_dash", 0.6, DASH),
    ("M13_inflation", 0.6, re.compile(r"\b(?:(?:stands|serves) as a (?:testament|reminder)|pivotal (?:moment|role|step)|plays? an? (?:key|crucial|vital|pivotal|significant|critical|central) role|marking an? (?:significant|pivotal|major|new)|setting the stage|evolving landscape|indelible|lasting legacy|future (?:looks|remains) (?:bright|promising)|continues? to thrive|paving the way)\b", I)),
    ("M15_ing_rider", 0.6, re.compile(r",\s(?:highlighting|underscoring|emphasizing|ensuring|reflecting|symbolizing|contributing to|cultivating|fostering|encompassing|showcasing|demonstrating|illustrating|reinforcing|signaling)\b", I)),
    ("M18_copula_avoidance", 0.6, re.compile(r"\b(?:serves|stands|functions|operates|acts) as\b|\bboasts\b", I)),
    ("M25_meta_document", 0.6, re.compile(r"\b(?:this (?:paper|essay|section|report) (?:will|aims to|seeks to) (?:discuss|explore|examine)|the following section|as (?:mentioned|discussed|noted) (?:above|earlier|previously))\b", I)),
    # --- added from GPTZero ground truth (run 2026-10-04, Humanizer_Test.docx, doc AI prob 100%) ---
    ("S6_balanced_symmetry", 1.0, re.compile(r"\bneither\b[^.;]{1,80}\bnor\b|\bfor some\b[^.;]{1,80}\bfor others\b|\b(?:pulls|cuts) (?:two|both) ways\b|\b(?:a|the) (?:middle path|middle ground|missing middle|happy medium)\b|^\w+(?: \w+){0,4} (?:is|are) \w+ but \w+\.$", I)),
    ("S7_staged_reflection", 1.0, re.compile(r"^what (?:surprised|struck|stood out to|interested) me(?: most)?\b|\bI found [^.;]{1,80}\b(?:inspiring|fascinating|eye-opening|compelling|striking|interesting)\b|\bchanged (?:how|the way) I\b|\bleft me (?:cautious|wondering|convinced|skeptical)\b|\bI now (?:see|understand|realize)\b", I)),
    ("S3b_maxim", 1.0, re.compile(r"\bcorrelation (?:is not|does not (?:equal|imply)) causation\b|\b(?:is|remains) (?:still )?essential\.$|\bthe (?:prudent|wise|sensible|balanced) (?:position|approach|path|course)\b|\bmeasured support\b|\brather than abandon\b", I)),
    ("M26_long_list", 0.6, re.compile(r"(?:[^,;()]{2,40},\s){3,}(?:and|or)\s", I)),
    ("M27_which_rider", 0.6, re.compile(r",\s(?:which|a pattern that|a finding that)\s(?:supports|limits|feeds|leads|means|makes|helps|suggests|reflects|shows|explains|allows|creates|raises)\b", I)),
    ("M28_clause_chain", 0.3, re.compile(r",\s(?:and|so|yet|while)\s(?:the|they|those|it|its|that|this|these|each|he|she|we|I|many|most|samples|heavy|Europe|parents|children)\b", I)),
    ("M29_ordinal_scaffold", 0.6, re.compile(r"^(?:the )?(?:first|second|third|fourth|fifth)\b|\bis the (?:first|second|third|fourth|fifth)\.$|^(?:two|three|four|five|several) (?:related |main |key |major )?(?:debates|constructs|themes|issues|lines of research|questions|factors)\b", I)),
    ("M30_pivot_opener", 0.6, re.compile(r"^(?:so|still|even so|given (?:this|that|these)[^,]{0,30}|until then|in practice|doing so|taken together|together|tying [^,]{1,60}|for (?:parents|teachers|practitioners|educators)[^,]{0,50}),?\s", I)),
    ("M31_abstract_copula", 0.6, re.compile(r"^[A-Z][a-z]+(?:[ -][a-z]+){0,2} (?:is|are|remains?) (?:a |an |the )?(?:still )?(?:central|key|core|essential|critical|important|primary|major|defining)\b", I)),
    ("W9_hedge_stack", 0.3, re.compile(r"\b(?:could|may|might|can) (?:potentially|possibly|arguably|conceivably)\b", I)),
    ("W23_knowledge_limit", 0.3, re.compile(r"\b(?:not (?:extensively |widely |well )?documented|based on (?:the )?available information|while specific details|it is (?:widely )?believed that|as of my)\b", I)),
]
VOCAB_WEIGHT = 0.4


def tell_hits(sentence):
    return [(tid, w) for tid, w, rx in TELLS for _ in rx.finditer(sentence)]


def lm_sentence_ppl(sentences, model_name):
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer

    dev = "cuda" if torch.cuda.is_available() else "cpu"
    tok = AutoTokenizer.from_pretrained(model_name)
    model = AutoModelForCausalLM.from_pretrained(model_name).to(dev).eval()
    ppl = []
    prev = ""
    for s in sentences:
        # condition on previous sentence so the first tokens aren't scored context-free
        ctx_ids = tok(prev, return_tensors="pt").input_ids[:, -256:] if prev else None
        s_ids = tok((" " if prev else "") + s, return_tensors="pt").input_ids[:, :512]
        ids = torch.cat([ctx_ids, s_ids], dim=1) if ctx_ids is not None else s_ids
        labels = ids.clone()
        if ctx_ids is not None:
            labels[:, : ctx_ids.shape[1]] = -100
        with torch.no_grad():
            loss = model(ids.to(dev), labels=labels.to(dev)).loss.item()
        ppl.append(math.exp(min(loss, 20)))
        prev = s
    return ppl


def clf_probs(sentences, paragraphs, model_name):
    import torch
    from transformers import AutoModelForSequenceClassification, AutoTokenizer

    dev = "cuda" if torch.cuda.is_available() else "cpu"
    tok = AutoTokenizer.from_pretrained(model_name)
    model = AutoModelForSequenceClassification.from_pretrained(model_name).to(dev).eval()
    labels = {i: l.lower() for i, l in model.config.id2label.items()}
    ai_idx = next((i for i, l in labels.items() if l in ("fake", "ai", "machine", "generated", "label_1")), 0)

    def p_ai(texts):
        out = []
        for i in range(0, len(texts), 16):
            enc = tok(texts[i : i + 16], return_tensors="pt", truncation=True, max_length=512, padding=True).to(dev)
            with torch.no_grad():
                pr = torch.softmax(model(**enc).logits, -1)[:, ai_idx]
            out.extend(pr.tolist())
        return out

    sent = p_ai(sentences)
    # 512-token windows over paragraphs approximate document-level classification
    windows, cur = [], ""
    for p in paragraphs:
        if len(tok(cur + " " + p).input_ids) > 480 and cur:
            windows.append(cur)
            cur = p
        else:
            cur = (cur + " " + p).strip()
    if cur:
        windows.append(cur)
    doc = st.mean(p_ai(windows)) if windows else st.mean(sent)
    return sent, doc


# ---------------------------------------------------------------- scoring ----
def score(text, mode, lm_name, clf_name, markers):
    paras = extract_prose(text)
    sents, para_idx = [], []
    for i, p in enumerate(paras):
        for s in split_sentences(p):
            sents.append(s)
            para_idx.append(i)
    if not sents:
        return {"error": "no scorable prose found"}

    words = sum(len(s.split()) for s in sents)
    lens = [len(s.split()) for s in sents]
    hits = [marker_hits(s, markers) for s in sents]
    thits = [tell_hits(s) for s in sents]
    # one-sentence short paragraphs that follow another paragraph = S2 closer
    for i in range(len(sents)):
        pi = para_idx[i]
        if pi > 0 and para_idx.count(pi) == 1 and len(sents[i].split()) <= 12:
            thits[i].append(("S2_closer", 1.0))
    sent_w = [VOCAB_WEIGHT * len(h) + sum(w for _, w in t) for h, t in zip(hits, thits)]
    n_hits = sum(len(h) for h in hits)
    tell_counts = {}
    for t in thits:
        for tid, _ in t:
            tell_counts[tid] = tell_counts.get(tid, 0) + 1
    lex_density = 100.0 * sum(sent_w) / max(words, 1)
    lex_score = band(lex_density, 3.0, 0.3)
    len_cv = cv(lens)
    len_score = band(len_cv, 0.25, 0.65)

    used_mode, notes = mode, []
    ppl = clf_s = None
    if mode in ("auto", "full"):
        try:
            ppl = lm_sentence_ppl(sents, lm_name)
            clf_s, clf_doc = clf_probs(sents, paras, clf_name)
            used_mode = "full"
        except Exception as e:  # missing deps, no network, OOM
            if mode == "full":
                raise
            used_mode = "heuristic"
            notes.append(f"full mode unavailable ({type(e).__name__}: {str(e)[:120]}); using heuristic proxy")

    per = []
    if used_mode == "full":
        # document perplexity as length-weighted geometric mean of sentence ppl
        doc_ppl = math.exp(sum(math.log(p) * l for p, l in zip(ppl, lens)) / words)
        ppl_score = band(doc_ppl, 15, 60, log=True)
        ppl_cv = cv(ppl)
        burst_score = 0.6 * band(ppl_cv, 0.25, 0.80) + 0.4 * len_score
        clf_score = 100.0 * clf_doc
        overall = 0.30 * ppl_score + 0.20 * burst_score + 0.25 * clf_score + 0.25 * lex_score
        subs = {
            "perplexity": {"score": round(ppl_score, 1), "doc_ppl": round(doc_ppl, 2)},
            "burstiness": {"score": round(burst_score, 1), "ppl_cv": round(ppl_cv, 3), "len_cv": round(len_cv, 3)},
            "classifier": {"score": round(clf_score, 1), "model": clf_name},
            "tells": {"score": round(lex_score, 1), "weighted_per_100w": round(lex_density, 2), "vocab_hits": n_hits, "structural": tell_counts},
        }
        for i, s in enumerate(sents):
            sp = band(ppl[i], 15, 60, log=True)
            sc = 100 * clf_s[i]
            sl = min(100, 45 * sent_w[i])
            sig = {"PPL": sp, "CLF": sc, "TELL": sl}
            per.append((s, 0.35 * sp + 0.35 * sc + 0.30 * sl, sig, hits[i] + [t for t, _ in thits[i]], round(ppl[i], 1)))
    else:
        # structural uniformity: mean-length CV across paragraphs. Sentence-count CV was dropped
        # (2026-10-11): the quality gate pins paragraphs to 5-8 sentences, so count CV only fought it.
        para_means = [st.mean([l for l, pi in zip(lens, para_idx) if pi == i]) for i in sorted(set(para_idx))]
        struct_score = band(cv(para_means), 0.08, 0.35)
        reg_score, reg_metrics = register(sents)
        # 2026-10-11: on fluent text, length CV and paragraph uniformity ran opposite to ZeroGPT
        # (detector_feedback.md), so they are down-weighted and register carries the load.
        overall = 0.10 * len_score + 0.40 * lex_score + 0.05 * struct_score + 0.45 * reg_score
        subs = {
            "register": {"score": round(reg_score, 1), **reg_metrics},
            "burstiness_length": {"score": round(len_score, 1), "len_cv": round(len_cv, 3)},
            "tells": {"score": round(lex_score, 1), "weighted_per_100w": round(lex_density, 2), "vocab_hits": n_hits, "structural": tell_counts},
            "paragraph_uniformity": {"score": round(struct_score, 1)},
        }
        for i, s in enumerate(sents):
            # sentence sits in a uniform run: neighbours within ±4 words of each other in the 15-30 band
            win = lens[max(0, i - 2) : i + 3]
            uniform = 100 if (len(win) >= 3 and max(win) - min(win) <= 8 and 14 <= st.mean(win) <= 30) else 20
            sl = min(100, 45 * sent_w[i])
            sig = {"BURST": uniform, "TELL": sl}
            per.append((s, 0.35 * uniform + 0.65 * sl, sig, hits[i] + [t for t, _ in thits[i]], None))

    qual = quality(sents, lens, para_idx)
    combined = AI_WEIGHT * overall + QUALITY_WEIGHT * qual["score"]

    flagged = sorted(
        (
            {
                "sentence": s,
                "score": round(sc, 1),
                "dominant_signal": max(sig, key=sig.get),
                "tells": h,
                **({"ppl": p} if p is not None else {}),
            }
            for s, sc, sig, h, p in per
        ),
        key=lambda d: -d["score"],
    )
    return {
        "mode": used_mode,
        "overall_ai_score": round(overall, 1),
        "subscores": subs,
        "quality": qual,
        "combined_score": round(combined, 1),
        "sentences_scored": len(sents),
        "words_scored": words,
        "flagged": [f for f in flagged if f["score"] >= 50][:25],
        "all_sentences": flagged,
        "notes": notes,
    }


def calibrate(res, gz):
    """Compare local per-sentence scores and tells to external sentence labels."""
    lab = {x["sentence"]: x["label"] for x in gz["sentences"] if x["label"] in ("AI", "HUMAN")}
    rows = [(d, lab[d["sentence"]]) for d in res["all_sentences"] if d["sentence"] in lab]
    ai = [d["score"] for d, l in rows if l == "AI"]
    hu = [d["score"] for d, l in rows if l == "HUMAN"]
    print(f"\n  calibration vs {gz.get('detector')} {gz.get('version')} (doc AI {gz.get('doc_ai_probability')}%): "
          f"{len(ai)} AI / {len(hu)} HUMAN sentences matched")
    if ai and hu:
        auc = sum((x > y) + 0.5 * (x == y) for x in ai for y in hu) / (len(ai) * len(hu))
        print(f"  mean local score  AI={st.mean(ai):.1f}  HUMAN={st.mean(hu):.1f}  AUC={auc:.2f} "
              f"(0.5 = no better than chance)")
    tids = sorted({t for d, _ in rows for t in d["tells"]})
    if tids:
        print("  tell                       in AI-labelled   in HUMAN-labelled")
        for t in tids:
            na = sum(1 for d, l in rows if l == "AI" and t in d["tells"])
            nh = sum(1 for d, l in rows if l == "HUMAN" and t in d["tells"])
            print(f"  {t:<26} {na:>3}/{len(ai):<12} {nh:>3}/{len(hu)}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("file")
    ap.add_argument("--json")
    ap.add_argument("--threshold", type=float, default=15)
    ap.add_argument("--mode", choices=["auto", "full", "heuristic"], default="auto")
    ap.add_argument("--lm", default="gpt2-medium")
    ap.add_argument("--clf", default="openai-community/roberta-base-openai-detector")
    ap.add_argument("--labels", help="gptzero_ingest.py JSON for this same text: print a calibration report "
                    "(how well local scores and each tell track the external detector's sentence labels)")
    a = ap.parse_args()

    res = score(open(a.file, encoding="utf-8").read(), a.mode, a.lm, a.clf, load_markers())
    if "error" in res:
        print(res["error"], file=sys.stderr)
        sys.exit(2)
    res["threshold"] = a.threshold
    res["pass"] = res["combined_score"] <= a.threshold and res["quality"]["gate_ok"]
    if a.json:
        json.dump(res, open(a.json, "w"), indent=2)

    q = res["quality"]
    print(f"mode={res['mode']}  COMBINED={res['combined_score']}  threshold={a.threshold}  "
          f"{'PASS' if res['pass'] else 'FAIL'}")
    print(f"  AI score  {res['overall_ai_score']:>5}   (weight {AI_WEIGHT})")
    print(f"  quality   {q['score']:>5}   (weight {QUALITY_WEIGHT}, higher = worse)   gate "
          f"{'ok' if q['gate_ok'] else 'FAIL'}")
    for p_ in q["gate_problems"]:
        print(f"    gate: {p_}")
    print("  quality components: " + ", ".join(f"{k} {v}" for k, v in q["components"].items()))
    for n_ in q["notes"]:
        print(f"    - {n_}")
    print("  AI subscores:")
    for k, v in res["subscores"].items():
        print(f"  {k:<22} {v['score']}")
    for f in res["flagged"][:10]:
        print(f"  [{f['score']:>5}] {f['dominant_signal']:<6} {f['sentence'][:90]}")
    for n in res["notes"]:
        print("  note:", n)
    if res["mode"] == "heuristic":
        print("  note: heuristic mode cannot certify a pass; confirm with an external detector run "
              "(see SKILL.md, external gate)")
    if a.labels:
        calibrate(res, json.load(open(a.labels)))
    sys.exit(0 if res["pass"] else 1)


if __name__ == "__main__":
    main()
