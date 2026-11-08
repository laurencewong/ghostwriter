# Stage 2: pick the thesis

**Read:** `input/thesis/options.md` and the author's choice (a note in `input/thesis/`, or the conversation).
**Write:** `thesis.md` (fill every section of the template).

This happens in the **synthesis** phase. In research, the author holds a *working hypothesis*
(`hypothesis --set`), not a pick. If the book is still in research, say so and stop.

If the author has not chosen, do not choose for them. Write a Decision / Options /
Recommendation / What unblocks block at the top of `thesis.md` and stop.

Once chosen:
- Sharpen the statement to one sentence of 25 words or fewer. Keep the author's key words.
- **What would prove it wrong** must be concrete enough that a reader could go check.
- **The strongest opposing view** is written so its best believer would sign it. If it reads
  like a straw man, rewrite it.
- Record the options that lost and the reason, so later chapters can revisit them.

**Pivots are normal.** When the author drops a picked thesis or a set of options, archive them
with the reason before writing anything new:

    python3 scripts/ghostwriter.py supersede <book> --reason "what changed the author's mind"

This moves `thesis.md` and `input/thesis/options.md` into `input/thesis/archive/` with the reason
and a timestamp, resets `thesis.md`, and logs the pivot in `ghostwriter.json`. The working
hypothesis stays separate from the pick; change it with `hypothesis --set ... --reason`.
