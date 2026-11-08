# Research stage R4: analogy gap-filling

Authors think in analogies: "X is like a reorg", "a new hire is like a transplant". Each
one is a research lead and a possible chapter. Treat it as a hypothesis to test, not a fact.

    python3 scripts/ghostwriter.py voice-log <book> "X is like Y" --kind analogy   # first, verbatim
    python3 scripts/ghostwriter.py scaffold <book> analogy --name "X is like Y"

**Write:** the scaffolded note in `research/`. Front matter: `analogy:` (the author's exact
words), `author_voice:` (the `V###`), `fills:` (the coverage cells it answers).

Sections, all required:
1. **What the other world does:** the named practices the source domain uses for this situation,
   each with an evidence grade and a source key.
2. **Translation:** the version the book's audience could use, one practice per bullet.
3. **Where the analogy breaks:** specific and at least 40 words. Who did not choose the change,
   what has no equivalent, which incentive or power is missing. If it breaks badly, say the
   analogy should be dropped. This section is the difference between insight and a slogan.
4. **Evidence strength:** grade every claim ([S]/[M]/[W]/[A]/[C]). Say plainly which parts are
   reasoned borrowing with no direct test.

Then update the coverage JSON: cells this filled change from `empty` to `filled` (mark them), and
re-run `coverage`. Run `check-research` on the note.
