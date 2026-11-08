# prompts/

The judgment steps of the pipeline. Each file is a self-contained instruction for an AI coding
agent (Claude Code or similar) working inside a book workspace. Run them in order. The
deterministic steps between them are `scripts/ghostwriter.py` commands, named in each prompt.

| Stage | Prompt | Writes | Then run |
|---|---|---|---|
| 1 | 01-thesis-options.md | input/thesis/options.md | |
| 2 | 02-pick-thesis.md | thesis.md | |
| 3 | 03-book-spine.md | spine.md | |
| 4 | 04-interview.md | interview/questions.md | `interview-open`, `interview-file` |
| 5 | 05-ingest-source.md | sources/S###.md | `add-source` |
| 6 | voice-profile.md | voice/profile.md notes | `voice-build` |
| 7 | 06-draft-chapter.md (K times, fresh context each) | drafts/chNN/run-K.md | |
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
   What unblocks, and stop.
