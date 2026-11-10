# Changelog

## 0.4.0 (2026-11-10): public release
- **Licensed:** MIT for the code (`scripts/`, `tests/`, `.claude/hooks/`, `.claude/settings.json`) in
  `LICENSE`; CC BY 4.0 for the prompts, docs, book template, examples and data in `LICENSE-CONTENT`.
  The README states the split.
- **Opt-in Claude Code hook for the support line** (`scripts/fund_line_hook.py`). When an agent runs
  the CLI through the Bash tool (not a terminal), the CLI now prints a neutral
  `[value moment] <id> key=<hash> words=<n> | <outcome>` marker, with no money in it, instead of
  nothing. The hook spots it and shows the line to the user as a `systemMessage`; the model never
  says it. Same caps, opt-outs, CI silence and covered-goal stop as the CLI, sharing its state file
  (`fund --off` turns off both). Each value moment in `FUNDING-STATUS.json` carries a `hook_match`.
  Off by default and not enabled in this repo's `.claude/settings.json`; the README has the snippet.
- `fund_count` is the one counter both surfaces use. 108 tests.
- Graded against the shared-repo standard v1.2.0 (`.repo-evals.json`).

## 0.3.0 (unreleased)
Lessons from the first real run with an author. The agent jumped to a thesis pick and chapter
spines on day one; the author said "we are in the research phase, not the writing phase".
- **Phases with exit criteria:** research -> synthesis -> proposal (optional) -> writing. New books
  start in research. `phase status` checks each phase's criteria (the author's own checklist in
  `research/PLAN.md`, a working hypothesis, the author's words logged, coverage at a threshold,
  citation statuses; then a picked thesis, a spine, research ingested). `phase advance` refuses
  until they pass; `--override` logs the author's reason. Going back a phase needs a reason.
  `tournament` and `promote` refuse before writing unless `--override-phase "why"` (logged).
  Books from earlier versions (no `phase` key) count as writing, so nothing breaks.
- **Thesis pivots:** `hypothesis --set` keeps a labeled working hypothesis separate from the pick and
  archives the old one with the reason; `supersede` archives the pick and options with the reason.
- **The author's words are the spine:** `voice-log` records quotes, metaphors, analogies, beliefs,
  corrections and stories verbatim with timestamps (`author-voice/`). New gate
  (`check-author-voice`, also in `tournament`/`promote` once the log applies): every entry a draft
  lists, or that is tagged for its chapter, must appear word for word. `[V###]` tags count as the
  author's own.
- **Citation honesty:** every source has a status, `verified` (with how), `confirm-before-print`, or
  `secondhand` (with via). Links default to confirm-before-print. `cite-status` updates it. The
  provenance gate fails chapters that cite confirm-before-print sources or carry `[CBP]` markers;
  research notes may hold them. Prompt R7 covers falling back to direct fetches of primary sources
  when web search is rate-limited.
- **Research toolkit:** prompts R0-R7 (research plan, author voice, borrow-from-other-worlds scan,
  coverage grid, analogy gap fill, popular-research scorecard, theory builder, citation honesty);
  `scaffold` templates for each; `check-research` structural checks (falsifier per proposition, 5-8
  dated predictions, a named decision rule, judgment-labeled scores, a thin-evidence section; a
  40+ word "where the analogy breaks"; HOLDS/CONTESTED/MISREAD plus replication; per-domain
  mechanisms, practices, evidence, dark side, translation).
- **Coverage:** `coverage` scores a JSON grid (filled / meaningful cells; n/a excluded, dups counted,
  unassessed cells not filled), ranks empty cells, flags duplicates to merge, items with no
  evidence, and items not mapped to exactly one mechanism; breadth mode scores required domains
  instead. Writes a Markdown report.
- **Research into sources:** `ingest-research` registers a note's Sources table as citable sources,
  keeps each status, and skips rows already registered.
- **Value moment:** leaving research with every criterion met (no override) is declared in
  `FUNDING-STATUS.json`. It names the outcome and makes no time claim (no research-time benchmark).
- Fictional research-phase demo in `examples/demo-research/`. 97 tests.

## 0.2.0 (unreleased)
- The value-moment line now leads with the value, as a labeled estimate: "That's about N hours of
  drafting you didn't do". Words in the passing chapter (or, for a full draft, every promoted chapter)
  ÷ a cited composing-speed benchmark (Karat et al. 1999, ~1,140 words/hour), claimed at 50% and
  rounded down; no value claim under 10 minutes. Assumptions live in `FUNDING-STATUS.json`
  (`value_estimates`), capped at a 50% claim share in code.
- `fund` prints the estimate's formula, benchmark source, why it is conservative, a worked example and
  the math for your own last chapter.
- Shorter ask: "Ghost Writer is free; building it cost ~$X in AI, $Y covered. Chip in $3: <link>".

## 0.1.0
- First version: thesis, spine, interview loop, source registry, voice profile, multi-run
  chapter drafts with AI-tell, provenance and thesis-honesty gates, tournament, promote,
  revision notes.
- Fictional demo book in `examples/demo-book/`.
- Standalone boundary hook with tests.
- `fund` command and an occasional one-line sponsor note at declared value moments (a chapter's
  first pass of all three gates; a complete draft). Capped, opt-out, silent in CI and when piped,
  stops once the build cost is covered, and never written by the model.
