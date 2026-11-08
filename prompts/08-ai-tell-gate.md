# Stage 8a: AI-tell gate (quality, not concealment)

    python3 scripts/ghostwriter.py check-ai-tells drafts/chNN/run-K.md

The script catches stock phrases. Then read the draft in a fresh context, as a skeptical
editor, and fix what the list cannot catch:
- Paragraphs that summarize what they just said.
- Lists of three that exist only for rhythm.
- Hedges with no information ("can be", "may often").
- Abstract nouns where the author would use a concrete example.
- An ending that inflates the stakes.

Fix by rewriting toward the voice profile and the sources, not by swapping synonyms.
This gate exists because generic prose is bad prose. It is not a way to hide that AI helped
write the book: the author decides how to disclose that (see README, Disclosure).
