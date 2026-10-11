# AI Vocabulary Markers

`scripts/score.py` reads the phrase list between the `BEGIN`/`END` markers below (one per line, case-insensitive, `#` comments ignored). Edit freely; the scorer picks up changes on the next run.

Vocabulary is the weakest, fastest-drifting signal; structural tells live in `patterns.md` and outrank this list. These aren't banned words. Each is fine once in a long human paper. They become a signal through **density** and **co-occurrence**.

<!-- BEGIN MARKERS -->
# Vocabulary over-represented in post-2023 LLM output
delve
delves
delving
tapestry
multifaceted
intricate
intricacies
nuanced
pivotal
crucial role
plays a crucial role
plays a vital role
plays a significant role
paramount
underscore
underscores
underscoring
highlight the importance
highlights the importance
shed light on
sheds light on
navigate the complexities
navigating the complexities
in the realm of
realm
landscape
ever-evolving
ever-changing
rapidly evolving
dynamic landscape
robust
seamless
seamlessly
leverage
leveraging
harness
harnessing
foster
fostering
holistic
comprehensive understanding
a testament to
stands as a testament
serves as a testament
meticulous
meticulously
commendable
noteworthy
notably
embark
journey
interplay
myriad
plethora
vibrant
bustling
unwavering
resonate
resonates
elevate
unlock
unleash
game-changer
cutting-edge
# Stock transitions and framing
it is important to note
it is worth noting
it's worth noting
it should be noted
in today's
in the modern era
in an era of
in conclusion
to summarize
in summary
overall,
ultimately,
furthermore,
moreover,
additionally,
consequently,
on the other hand
that being said
with that said
when it comes to
at its core
not only
but also
a wide range of
a variety of
various aspects
various factors
key factors
key aspects
by doing so
this ensures
ensuring that
by understanding
# Hedge stacks
may potentially
could potentially
can potentially
might potentially
it can be argued
one could argue
# Chat residue (should be gone after sanitizer)
as an ai
i hope this helps
let me know
feel free to
certainly!
great question
<!-- END MARKERS -->

Structural tells (not-X-but-Y, closers, triads, dashes, -ing riders, copula avoidance) are defined and detected per `references/patterns.md`.
