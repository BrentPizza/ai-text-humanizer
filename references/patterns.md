# Pattern Catalog: Structural AI Tells

Adapted from the approach in blader/humanizer (MIT) and Wikipedia's "Signs of AI writing" (WikiProject AI Cleanup), rewritten for APA academic and technical prose. Examples here are original.

## Why these patterns exist

A language model picks the continuation that fits the widest set of readers. Each tell below is a default choice that a writer focused on one reader and one subject would not make. Vocabulary tells drift with every model release; structural tells persist. Work structure first, vocabulary second.

**Two rules govern every edit:**
1. Every sentence you keep must add something the reader does not already have.
2. A tell counts in proportion to how rarely a careful writer makes it on purpose. **Strong** patterns justify an edit on one sighting. **Medium** patterns justify an edit when they repeat. **Weak** patterns need at least one other tell in the same paragraph.

`scripts/score.py` detects the patterns marked `[det]` by regex and weights them strong 1.0 / medium 0.6 / weak 0.3. The rest are for the rewriter's read-through.

---

## A. Staging instead of stating (STRONG)

### S1. Not X but Y [det]
Forms: "not X but Y", "not just/only/merely X, but Y", "it's not X, it's Y", the two-sentence version ("This does not mean X. It means Y."), and the clipped tail (", not guesswork").
Why: the negative half rebuts a claim no one made, so the positive half sounds bigger without adding information.
Fix: state the positive claim. Keep the contrast only when the reader actually holds the belief being corrected, or both halves carry information.
- Before: Segmentation is not just a network control; it is a strategic imperative.
- After: Segmentation limits how far an intruder can move after initial access.

### S2. Closers and restating fragments [det: one-sentence paragraphs ≤12 words; "this shows/demonstrates…" openers]
Forms: a one-line paragraph restating the previous one; "That distinction matters."; a sentence after an example that names what the example showed; rows of fragments.
Fix: cut it, unless it adds a consequence the example did not show.
- Before: The 2021 Oldsmar incident involved remote access to a water treatment HMI. This illustrates the importance of access controls.
- After: The 2021 Oldsmar incident involved remote access to a water treatment HMI through shared TeamViewer credentials.

### S3. Sayings that sound deep [det]
Forms: "the real question is", "at its core", "at the heart of", "what really matters", "fundamentally", "X is the language/currency/architecture of Y".
Fix: replace with the specific claim the saying gestures at.

### S4. Staged run-ups [det]
Forms: "Let's explore", "Here's the thing", "It is worth examining", "Honestly?", "Consider the following".
Fix: delete the run-up and start at the point.

### S5. Arguing with no one [det]
Forms: "This is not to say", "To be clear", "One might be tempted to", "It would be easy to assume".
Fix: remove the defense. If it hides a real claim, state the claim. Keep objections the text attributes to a cited source and actually answers.

## B. Rhythm by rule

### M6. Forced triads (MEDIUM) [det]
Three items because three sounds complete. Check each item adds a distinct idea; merge or cut padding. Two or four is fine.

### M7. Repeated sentence openings (MEDIUM)
Several consecutive sentences starting with the same subject or transition. Merge or change the subject.

### M8. Dashes (MEDIUM, density) [det]
**Rule:** no em dashes (—), en dashes used as clause breaks (–), or double hyphens in the final text, unless the user supplies a writing sample that uses them; then match its rate. Replace with a comma, colon, parentheses, or a period. En dashes in number ranges (pp. 14–22) and hyphens in compounds are fine.

### W9. Stacked hedges (WEAK) [det]
"could potentially", "may possibly", "might arguably". Keep one hedge the evidence supports.

### W10. Post-noun hyphenation (WEAK)
"the data is well-documented" → "well documented". Keep the hyphen before the noun.

### W11. Agentless passive (WEAK)
APA 7 allows first person for the author's own actions. "An analysis was conducted" → "I analyzed".

## C. Inflation

### M12. Overused vocabulary (MEDIUM in clusters) [det: references/ai_markers.md]
delve, tapestry, pivotal, crucial, underscore (verb), landscape (abstract), robust (non-technical), intricate, meticulous, testament, showcase, interplay, vibrant, garner, enhance. One is noise; a cluster is a tell.

### M13. Inflated significance (MEDIUM) [det]
"marking a pivotal moment", "plays a key role", "setting the stage for", "lasting legacy", "evolving landscape", "the future looks promising", "continues to thrive despite challenges".
Fix: keep the fact, drop the significance. End sections on the last concrete fact.

### W14. Vague association (WEAK)
"associated with", "linked to", "in connection with" where the source gives the actual relationship. Name it. If the source doesn't say, leave it.

### M15. -ing riders (MEDIUM) [det]
", highlighting…", ", underscoring…", ", reflecting…", ", ensuring…", ", contributing to…" tacked onto a fact to make it sound deeper. Keep only if the cited source supports the rider's claim.

### M16. Promotional language (MEDIUM)
"groundbreaking", "renowned", "state-of-the-art", "seamless", "cutting-edge". State what the thing is.

### M17. Borrowed authority (MEDIUM)
"Experts argue", "research shows", "studies suggest" with no citation. In APA this is also a citation error: attach the actual source or cut the claim. Flag for the orchestrator; never invent the citation.

### M18. Copula avoidance (MEDIUM) [det]
"serves as", "stands as", "functions as", "boasts", "represents a". Use is/are/has.

## D. Formatting by rule
Bold lead-ins with colons, title-case everything, emoji, decorative rules. The sanitizer strips most of this; APA heading case rules then apply.

## E. Leftovers
### S22. Chat residue (STRONG) — handled by sanitizer.
### W23. Knowledge-limit hedges (WEAK) [det]
"not extensively documented", "based on available information", "it is believed that", "likely" filling a gap with a guess. State what the sources don't show, or cut.
### M24. Heading echoed in the first sentence (MEDIUM)
Delete the restating sentence.
### M25. Writing about the document (MEDIUM)
"This paper will discuss", "The following section examines", "As mentioned above". APA permits a brief roadmap at the end of the introduction; elsewhere, cut it.

## F. Added from external-detector ground truth

Source: GPTZero `2026-09-13-base` report on Humanizer_Test.docx (2026-10-04), which scored a text this catalog already passed (local 25.9) at **100% AI**. 59 of 70 scored sentences were labelled AI. The patterns below were over-represented in AI-labelled sentences and absent or rare in HUMAN-labelled ones. See `references/detector_feedback.md` for the counts. They are fitted to one report, so treat weights as provisional and re-check them with `score.py --labels` on every new report.

### S6. Balanced symmetry (STRONG) [det]
Forms: "neither X nor Y", "for some families and for others", "pulls two ways", "a middle path", "the missing middle", short "X is A but B." verdicts ("These studies are relevant but imperfect.").
Why: the model resolves every tension into a tidy both-sides frame. A writer with a position states which side the evidence favors and by how much.
Fix: state the asymmetric claim the evidence supports, or name the specific condition that decides between the two sides.
- Before: Free-range practice is a deliberate choice for some families and a necessity for others.
- After: Families with irregular shift work often have no supervised option, so "free-range" describes their constraint, not their philosophy.

### S7. Staged reflection (STRONG, reflection sections) [det]
Forms: "What surprised me most was", "I found X inspiring because", "changed how I read", "left me cautious about", "I now see".
Why: it performs a reaction instead of reporting one. Real reflection names the specific prior belief and the specific finding that moved it.
Fix: replace with the concrete before/after: what the writer assumed, which number or result contradicted it, and what they would now do differently. Keep first person.

### S3b. Closing maxims (STRONG) [det]
Forms: "Correlation is not causation.", "X is still essential.", "the prudent position is", "measured support for", "calibrate rather than abandon".
Fix: cut, or replace with the specific limitation of the specific study.

### M26. Long lists (MEDIUM) [det]
Four or more comma-separated items ("running, climbing, jumping, balancing, and throwing"). Lists are default completion: the model keeps naming members of the category. Keep the one or two items the argument uses; move the rest into a citation-backed clause or drop them if they add nothing the argument uses.

### M27. Which-riders (MEDIUM) [det]
", which supports/limits/feeds/leads…" tacked onto a fact to interpret it. Same mechanism as M15. Make the interpretation its own sentence with an explicit subject, or cut it.

### M28. Clause chains (WEAK, density) [det]
Two independent clauses joined by ", and the/they/those…". One per paragraph is normal. Three or more in a paragraph produce the even, rolling cadence detectors score as low burstiness. Split some into separate sentences of very different length; subordinate others ("Because…", "Although…").

### M29. Ordinal scaffolding (MEDIUM) [det]
"Four related debates run through the literature. The first is… The second… Equity is the third… The fourth is…". Enumerated paragraph skeletons are a strong document-level fingerprint. Order the issues by importance or causality and connect them with the reason one leads to the next.

### M30. Pivot openers (MEDIUM) [det]
Sentence-initial "So,", "Still,", "Even so,", "Given this…,", "Until then,", "In practice,", "Doing so", "Tying X back to Y", "For parents, teachers, and…". Each is a hinge the model inserts to manage flow. Start on the subject or the evidence.

### M31. Abstract-subject evaluations (MEDIUM) [det]
"Emotion regulation is a central task of these years." "Skeptical inquiry is still essential." An abstract noun plus "is a key/central/essential…". Replace with what the thing does or what was found about it.

### M32. Textbook exposition run (MEDIUM, paragraph level)
A paragraph that walks a theory in order (theorist → stage → characteristics → implication) with every sentence at 15–25 words and no authorial claim. GPTZero flagged every sentence of all three "Domain" paragraphs although they carried almost no catalog tells. This is a perplexity problem, not a vocabulary problem. Fix at paragraph level: open on the claim the theory is being used to support, cite the theory in service of that claim, cut summary sentences a textbook would contain but the argument doesn't need, and end on the concrete fact rather than a synthesis.

## G. Added from ZeroGPT ground truth (2026-10-11, Cost Trial.docx)

### S8. Staccato over-correction (STRONG, rewriter-induced) [det: score.py quality gate]
Forms: runs of 5 to 9 word declaratives; a fact and its consequence split across two sentences with the logic dropped ("They can be traced to particular dishes. Those items are therefore variable and direct."); a list split into one sentence per member ("Takeout packaging does too."); a process told as bare steps with no connective ("They go to the table or the takeout window. They end in finished goods…").
Why: it is what this skill produced when M28, M27, M15 and M30 fixes were applied by splitting instead of rewriting. It slipped under ZeroGPT (39%) because it is odd, not because it is human, and it reads as broken to an instructor.
Fix: rebuild the paragraph around its point. Put cause and effect in one sentence with a subordinate clause; fold list members into one sentence; keep logical connectives.
- Before: Shrimp, flounder, and scallops change with volume. They can be traced to particular dishes. Those items are therefore variable and direct.
- After: Seafood like shrimp, flounder, and scallops goes up and down with how much the kitchen sells, and each one can be traced to the dish it goes into, so it counts as variable and direct.

### S9. Polished register (STRONG on ZeroGPT) [det: score.py register]
Forms: noun-heavy, low function-word prose; crafted short verdicts ("Pricing starts with unit cost.", "Private events and catering are the exception."); elegant verbs chosen for rhythm ("costs travel with the food", "costs have landed in"); no author anywhere.
Why: a fluent, tidy rewrite of the same facts scored 84.6% on ZeroGPT; the same facts in a plain explanatory student voice scored 18.6%. Measured difference: function-word share 0.35 vs 0.47, average word length 5.1 vs 4.5 letters, author presence 4% vs 22% of sentences.
Fix: explain instead of summarize. Leave function words in, use plain verbs, let the author appear where the genre allows, and walk through one concrete example. Do not drop below the S8 fluency floor to get there.

### What GPTZero labelled HUMAN in the same text
The human-labelled sentences shared: a concrete specific (a state, a year, a sample size of 422), an authorial stance stated plainly ("less conclusive than either side of the debate tends to admit"), one idiomatic or register-lowering word ("kids"), and a reason clause fronted rather than trailed ("Because the headline cases involve school-age kids, …"). Use these as positive targets, not tricks: they are what writing with a point of view looks like.

## When not to act

- Inside direct quotations, titles, proper nouns, or text that discusses a phrase rather than uses it.
- Field terminology that happens to overlap the list: "robust" in statistics (robust standard errors), "landscape" in ecology, "underscore" as a character.
- Text dated before November 30, 2022 is not LLM output.
- Keep voice markers: a specific odd detail, a real first-person methodological choice, a qualified judgment the evidence supports, a parenthetical self-correction.
- Several tells together are the signal. One alone usually isn't.
