# prompts/

The judgment steps of the pipeline. Each file is a self-contained instruction for an AI coding
agent (Claude Code or similar) working inside a book workspace. Run them in order. The
deterministic steps between them are `scripts/ghostwriter.py` commands, named in each prompt.

A book moves through four phases: **research -> synthesis -> proposal (optional) -> writing**.
`python3 scripts/ghostwriter.py phase status <book>` shows the phase and its exit criteria. Run it
before producing any large artifact. Drafting commands refuse to run before the writing phase
unless the author overrides (logged).

**Research phase** (a new book starts here; no drafting):

| Stage | Prompt | Writes | Then run |
|---|---|---|---|
| R0 | R0-research-plan.md | research/PLAN.md, working hypothesis | `phase status`, `hypothesis --set` |
| R1 | R1-author-voice.md (all the time, every phase) | author-voice/log.jsonl | `voice-log` |
| R2 | R2-borrow-scan.md | research/<date>-<slug>.md | `scaffold borrow`, `check-research` |
| R3 | R3-coverage-grid.md | research/coverage/<slug>.json | `scaffold coverage`, `coverage` |
| R4 | R4-analogy-gap-fill.md | research/<date>-<slug>.md | `scaffold analogy`, `check-research` |
| R5 | R5-research-scorecard.md | research/<date>-<slug>.md | `scaffold scorecard`, `check-research` |
| R6 | R6-theory-builder.md | research/<date>-<slug>.md | `scaffold theory`, `check-research` |
| R7 | R7-citation-honesty.md (all research) | Sources tables, statuses | `cite-status`, `ingest-research` |

Then `phase advance` (the author ticks the exit criteria in research/PLAN.md).

**Synthesis, proposal and writing phases:**

| Stage | Prompt | Writes | Then run |
|---|---|---|---|
| 1 | 01-thesis-options.md (synthesis) | input/thesis/options.md | |
| 2 | 02-pick-thesis.md (synthesis) | thesis.md | `supersede` on a pivot |
| 3 | 03-book-spine.md (synthesis) | spine.md | `ingest-research`, then `phase advance` |
| 4 | 04-interview.md | interview/questions.md | `interview-open`, `interview-file` |
| 5 | 05-ingest-source.md | sources/S###.md | `add-source` |
| 6 | voice-profile.md | voice/profile.md notes | `voice-build` |
| 7 | 06-draft-chapter.md (writing phase; K times, fresh context each) | drafts/chNN/run-K.md | `phase require <book> writing` first |
| 8 | 08-ai-tell-gate.md, 09-provenance-gate.md, 10-thesis-honesty.md | fixes in place | `tournament` |
| 9 | 07-tournament.md | drafts/chNN/scoreboard.md verdict | `promote` |
| 10 | 11-revision-notes.md | revision-notes/chNN.md | |

Rules that apply to every prompt:
1. Never invent a fact. A claim either cites a registered source as `[S###]`, or is marked
   `[opinion]` (the author's view) or `[author]` (the author's own experience, ideally backed
   by an interview source).
2. Never imitate a named writer. The only voice is the author's, from voice/profile.md.
3. Never publish, post, send or push anything. Output is files in the workspace.
4. When the author must decide, write the decision as Decision / Options / Recommendation /
   What unblocks, and stop. One decision at a time.
5. Check the phase before producing anything big. In research, no chapter titles, spines or drafts
   unless the author asks for them after hearing which phase the book is in.
6. The author's words in `author-voice/` are kept verbatim. Build around them; never paraphrase them away.
7. Every citation has a status (verified, with how / confirm-before-print / secondhand). Research
   notes may hold confirm-before-print; chapters may not.
