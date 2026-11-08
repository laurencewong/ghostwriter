# Research stage R2: "borrow from other worlds" scan

Most hard problems in a book's subject have been solved, partly, somewhere else: by another kind
of organization, another field, another culture. This scan finds those solutions and tests what
would carry over.

    python3 scripts/ghostwriter.py scaffold <book> borrow --name "how other worlds keep members"

**Read:** the working hypothesis, `author-voice/log.md`, `research/PLAN.md`.
**Write:** the scaffolded note in `research/`.

1. State the core problem in the author's words (cite the `V###`).
2. Choose 6 to 15 domains that face the same structural problem. Pick from a recognized taxonomy
   where one exists (for example, kinds of groups from sociology), and include at least one
   domain where the practice turns coercive (the dark side teaches the limits).
3. For each domain, under `### <domain>` in `## Domains`, write:
   - **Mechanisms:** what it does that works, in plain words.
   - **Signature practices:** the named, specific practices insiders would recognize.
   - **Evidence:** graded [S] strong, [M] moderate, [W] weak or correlational, [A] anecdotal or
     doctrine, [C] contested, with source keys.
   - **Failure modes / dark side:** how it goes wrong, and its coercive version.
   - **Translation:** what the book's audience could borrow, and what they should leave behind.
4. Write `## The common toolkit`: what shows up in three or more domains.
5. Fill the `## Sources` table with a status per row (`prompts/R7-citation-honesty.md`).
6. Run `python3 scripts/ghostwriter.py check-research research/<note>.md`.

This feeds the coverage grid (`R3`): every signature practice becomes an item there.
