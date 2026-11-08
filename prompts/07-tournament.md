# Stage 9: tournament

First run the deterministic gates on every run:

    python3 scripts/ghostwriter.py tournament <book> chNN

Only drafts marked eligible on `drafts/chNN/scoreboard.md` can win. If none are eligible, fix
the failures (stages 8) or redraft; do not judge ineligible drafts.

Judge eligible drafts head to head, in a fresh context, blind to run number where possible.
Score 1 to 5 on each axis and write one line of evidence per score:
1. **Argument:** does the chapter move the thesis (or honestly test it)?
2. **Evidence:** are the strongest claims backed by the best sources available?
3. **Steelman:** would the opposing side sign the objection section?
4. **Voice:** does it sound like voice/profile.md, not like a generic assistant?
5. **Readability:** would a busy reader finish it?

Write the verdict under `## Judge verdict`: the winner, the runner-up, and the one thing to
steal from each loser (a scene, a line of argument, a source). Then merge the steals into the
winner, re-run `tournament`, and promote:

    python3 scripts/ghostwriter.py promote <book> chNN run-K
