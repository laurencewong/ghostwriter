# Stage 8c: keep the thesis honest

    python3 scripts/ghostwriter.py check-thesis drafts/chNN/run-K.md

The script checks structure: a `thesis_role`, a `claim`, a 60+ word objection section, and a
closing `## Where this leaves the thesis`.

Then judge substance:
- Does this chapter do what its `thesis_role` says? An `advances` chapter that only restates
  the thesis fails. A `tests` chapter that picks an easy test fails.
- Is the objection the **strongest** one available, from the spine and the sources? Would its
  best believer sign it?
- If the evidence in this chapter cuts against the thesis, does the chapter say so? If the
  thesis should change, write a Decision block for the author in `revision-notes/chNN.md`.
  Never bend the evidence to save the thesis.
