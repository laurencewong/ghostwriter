# Research stage R0: the research plan and its exit criteria

A new book starts in the **research phase**. Research comes before thesis picks, spines and
chapters. The most common failure in a first session is jumping to "pick a thesis" and chapter
titles on day one. Do not. If the author says "we are in the research phase", they are right.

**Read:** `ghostwriter.json`, `input/thesis/`, `author-voice/log.md`, anything the author shared.
**Write:** `research/PLAN.md` and `input/thesis/working-hypothesis.md` (through the CLI).

1. Run `python3 scripts/ghostwriter.py phase status <book>` first. Do this before every large
   artifact, in every session.
2. Log the author's own words as they come (`prompts/R1-author-voice.md`). The first things an
   author says about a book are usually its spine.
3. Write the questions the research must answer, in plain words, from the author's framing.
4. Write a **working hypothesis**, one or two sentences:

       python3 scripts/ghostwriter.py hypothesis <book> --set "..."

   It is labeled "working hypothesis, not a pick". It can change any time. When it does, pass
   `--reason` with what changed the author's mind; the old one is archived with that reason.
   Expect pivots. Two in an hour is normal.
5. Draft **exit criteria** with the author, as a checklist under `## Exit criteria`. Good criteria
   are observable: "the hypothesis survives a counterexample hunt", "the reader is defined from
   10+ conversations", "the author's interview is done", "2 expert checks". The author ticks them,
   not you. The CLI adds its own: a working hypothesis exists, the author's words are logged,
   coverage meets the threshold in `ghostwriter.json`, and every research citation has a status.
6. Keep `## In progress` to one item. Hand the author one decision at a time, in the four-line
   format (Decision / Options / Recommendation / What unblocks), then stop and wait.

**Not in this phase:** chapter titles, spines, chapter drafts, a picked thesis. If the author asks
for one anyway, it is their call: say what phase the book is in, and if they still want it, label
the output "exploratory, research phase" and keep it in `research/`.

**Moving on** is the author's decision: `phase advance <book>` refuses until every criterion
passes. The author can override with `--override "why"`, which is logged.
