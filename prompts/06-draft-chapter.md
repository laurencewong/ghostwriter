# Stage 7: draft a chapter (run K times, fresh context each)

**Read:** `thesis.md`, the chapter's row in `spine.md`, `voice/profile.md`, and the sources the
row lists (plus any others in `sources/` that fit).
**Write:** `drafts/chNN/run-K.md`. Each run is independent: do not read the other runs.

To make runs differ on purpose, each run gets a different **angle**: run 1 opens on a scene
from an interview source, run 2 opens on the strongest objection, run 3 opens on a number.
More runs: invent new angles.

Front matter (required, the gates read it):

    ---
    chapter: chNN
    run: K
    thesis_role: advances | tests | complicates
    claim: the one sentence this chapter argues
    angle: the opening angle for this run
    ---

Body rules:
- Every sentence with a number, a date, a study, a survey or a "most people" claim ends with
  `[S###]`, or `[opinion]` / `[author]` if it is the author's own view or experience.
  If you need a fact you do not have, write `[NEEDS SOURCE: what]` and keep going.
  (That marker fails the provenance gate on purpose.)
- Include `## The strongest objection`: the opposing case at full strength, 60+ words, then
  the author's answer. If the answer is weak, say so.
- End with `## Where this leaves the thesis`: advanced, tested, or bent, and how.
- Match the rhythm and stance numbers in `voice/profile.md`. Do not copy sample sentences.
- 1,500 to 4,000 words unless the spine says otherwise.
