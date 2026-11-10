# Ghost Writer

An AI ghostwriting agent for nonfiction authors: it researches first, keeps your own words verbatim, and turns your thesis, interview answers and published writing into book chapters where every fact has a source, the voice is yours, and the thesis gets tested instead of just sold.

It runs inside an AI coding agent (built for Claude Code). The judgment steps are plain-text prompts. The steps that should never be left to a model's judgment (the source registry, the voice measurements, and the gates a chapter must pass) are a small Python script with no dependencies.

## Quickstart

Needs Python 3.9+, `jq` (for the boundary hook), and Claude Code or a similar agent. Setup takes about five minutes.

```sh
git clone https://github.com/laurencewong/ghostwriter.git && cd ghostwriter
python3 scripts/ghostwriter.py init books/my-book --title "Working title" --author "Your Name"
# put a few of your own published pieces in books/my-book/voice/samples/
python3 scripts/ghostwriter.py voice-build books/my-book
python3 scripts/ghostwriter.py phase status books/my-book     # a new book starts in research
```

Then open the repo in Claude Code and say: "Start the research plan for books/my-book" (see `prompts/00-README.md` for every stage). Two fictional examples show the whole arc: `examples/demo-research/` is a book in the research phase (a coverage grid, an analogy gap fill, a mini theory), and `examples/demo-book/` is a book in the writing phase with a chapter that passed every gate.

## How it works

A book moves through four phases: **research → synthesis → proposal (optional) → writing**. Each has exit criteria that `phase status` checks. Drafting commands refuse to run until the book reaches writing, unless you override, and every override is logged. Only you move the book to the next phase.

### Research (where every book starts)

Built from a first real run, where the agent jumped to chapter titles on day one and the author had to say "we are in the research phase, not the writing phase."

- **A plan with exit criteria.** You write and tick the criteria ("the hypothesis survives a counterexample hunt", "the reader is defined"). The CLI adds its own: a working hypothesis exists, your words are logged, coverage meets the threshold, every citation has a status.
- **A working hypothesis, not a pick.** It is labeled as one, and it can change. When it does, the old one is archived with the reason (`hypothesis --set ... --reason`, `supersede`). Pivoting twice in an hour is normal.
- **Your words, verbatim.** Quotes, metaphors, analogies and corrections go into `author-voice/` with a timestamp (`voice-log`). Drafts build around them, and a gate fails any draft that paraphrased them away.
- **Borrow from other worlds.** How other kinds of organizations and fields already solved your book's core problem: their mechanisms, signature practices, evidence, dark sides, and what carries over to your reader.
- **A coverage grid ("are we MECE?").** A mechanism key (each practice maps to exactly one) × a situation list grounded in an established framework. `coverage` scores filled ÷ meaningful cells, ranks the empty cells that matter, flags duplicates to merge and practices with no evidence. A breadth mode scores coverage of the major domains instead, for when breadth matters more than MECE.
- **Analogy gap-filling.** Your "X is like a reorg" becomes a research note: what that world does, the translation, **where the analogy breaks** (required), and how strong the evidence is.
- **A popular-research scorecard.** The famous findings your readers already know, rated HOLDS / CONTESTED / MISREAD with their replication status. The overhyped ones become foils.
- **A theory you can attack.** Propositions that each name what would prove them wrong, 5 to 8 dated predictions, a named decision rule a reader can apply, scores labeled as judgment calls, and an honest "where the evidence is thin" section.
- **Honest citations.** Every source is `verified` (and how: fetched, PubMed, Crossref), `confirm-before-print`, or `secondhand` (and via what). Research notes may hold unconfirmed citations; chapters may not. `ingest-research` turns a note's Sources table into citable source IDs.

`check-research` checks each note's structure. `scaffold` starts each kind from a template.

### Synthesis and writing

1. **Thesis.** You drop candidate ideas in `input/thesis/`. The agent lays out the options, who would disagree with each, and what evidence each needs. **You pick.**
2. **Spine.** The thesis becomes 8 to 12 chapters. Every chapter is labeled `advances`, `tests` or `complicates` the thesis. At least one in four must test or complicate it.
3. **Interview loop.** Gaps in the evidence become interview questions for you. Your answers are filed as sources the chapters can cite.
4. **Sources.** Posts, notes, datasets, articles: each gets an ID (`S001`, `S002`, ...). Private material can be registered by pointer, without copying it.
5. **Voice.** `voice-build` measures your rhythm and habits (sentence length, questions, contractions, signature phrases) from **your own writing only**. It refuses samples not marked as yours.
6. **Chapters, multi-run.** The agent writes K independent drafts, each from a different opening angle. Every draft goes through three gates:
   - **AI-tell gate:** stock machine phrasing fails the draft.
   - **Fact and provenance gate:** every sentence that looks factual must cite a source ID or be tagged `[opinion]` / `[author]`. Unknown IDs and `[NEEDS SOURCE]` markers fail.
   - **Keep-the-thesis-honest gate:** the chapter needs a stated role and claim, a steelmanned objection section (60+ words), and a closing verdict on what happened to the thesis.

   - **Author-voice gate** (once your words are logged for the chapter): every entry the draft builds on appears word for word.
   - Citing a `confirm-before-print` source fails the provenance gate.

   Drafts that pass every gate go to a head-to-head tournament. The winner absorbs the best idea from each loser and is promoted. `promote` refuses any draft that fails a gate.
7. **Revision notes.** What the chapter now proves, open evidence gaps, and a Decision block whenever the evidence pushes against the thesis.

```
research: plan + exit criteria -> borrow scan -> coverage grid -> analogy gap fills -> scorecard -> theory
          (your words logged verbatim throughout; every citation has a status)
                                   |  phase advance (you decide)
thesis -> spine -> interview <-> sources -> voice
                                   |
            K drafts -> gates (AI-tell, provenance, thesis) -> tournament -> promote -> revision notes
```

## Limitations

- **It does not write your book for you.** Your lived experience comes from your interview answers. Where it has no source, it leaves a marker instead of inventing one.
- **The gates are tripwires, not truth.** The provenance gate finds sentences that look factual and checks that they carry a tag. It cannot tell whether a source actually says what the sentence claims. That is a prompt-driven check (`prompts/09`) and, in the end, yours.
- **Voice is measured, not cloned.** The profile is a handful of numbers and habits. Drafts will still need your edit to sound like you.
- **English only.** The sentence splitter and phrase list assume English prose.
- **Phase gating lives in the CLI.** `tournament` and `promote` refuse before the writing phase, and the prompts tell the agent to check the phase first. Nothing stops an agent from writing a draft file anyway; the gates just won't promote it.
- **Coverage is only as honest as the grid.** The score counts what the JSON says. "Filled" means a credible borrowed practice exists, not that it works for your reader. The report says so.
- **Citation statuses are self-reported.** The script enforces that a status exists and blocks `confirm-before-print` in chapters; it cannot tell whether "verified" was really checked.
- **The author-voice gate matches words, not meaning.** It catches a paraphrase; it cannot tell whether a verbatim quote is used fairly.
- **The boundary hook is a tripwire.** It blocks obvious outward and destructive commands; it is not a sandbox.
- No publishing, formatting for print, or agent scheduling. Output is Markdown files.

## Privacy and data

- Everything stays on your machine, in your book workspace. The script makes no network calls.
- Your AI agent sends what it reads to its model provider, under that provider's terms. Register sensitive material with `--pointer` and decide what the agent may open.
- Keep real books in `books/` (git-ignored) or outside the repo. Personal logs (`decisions-log.md`, `journal/`, `escalations/`) are git-ignored too.
- Source records store a file name as the origin, not your full local path.

## Disclosure

The AI-tell gate exists because generic prose is bad prose. It is not a tool for hiding that AI helped. How you disclose AI assistance is your call. We suggest saying so plainly in the acknowledgments.

## No imitation

Ghost Writer never imitates another writer. It will not take a "write like [famous author]" instruction, and it will not learn a voice from anyone's work but yours. Pastiche is weak writing, and copying a living writer's style from their text invites a copyright problem.

## Supporting Ghost Writer

Ghost Writer is free. Building it costs real money in AI time, so the CLI may print **one plain line** at a moment where you have just gotten something out of it, for example:

```
Chapter 3 passed all 3 checks ✓. That's about 3 hours of drafting you didn't do (estimate: `ghostwriter.py fund`). Ghost Writer is free; building it cost ~$6.15 in AI, $0 covered. Chip in $3: https://github.com/sponsors/laurencewong
```

- **When:** only at the value moments declared in [`FUNDING-STATUS.json`](FUNDING-STATUS.json): when the book leaves the research phase with every exit criterion met (not on an override), the first time a chapter passes every gate, and when the whole draft is done. Never mid-task.
- **The "hours" figure is an estimate, and a low one.** Words in the passing chapter ÷ a published composing-speed benchmark (19 words a minute, Karat et al. 1999), and only half of that is claimed, rounded down. Under 10 minutes, the line makes no value claim. The research moment makes no time claim at all, because there is no research-time benchmark we would trust; it names the outcome only. The assumptions sit in `FUNDING-STATUS.json` under `value_estimates`; `python3 scripts/ghostwriter.py fund` prints the math and the source.
- **How often:** the first of those moments, then about every 10th, and never more than once a week.
- **Never from the model.** The prompts and charter never mention money (a test checks). Only the script prints the line.
- **Silent** when output is piped or not a terminal (a neutral marker prints instead; see the opt-in hook below), in CI, with `GHOSTWRITER_NO_FUND=1` or `--quiet`, after `python3 scripts/ghostwriter.py fund --off`, and for good once the build cost is covered.
- `python3 scripts/ghostwriter.py fund` shows the cost, what sponsors have covered, the link and the estimate's math, any time. State lives in `~/.config/ghostwriter/fund.json` (honors `XDG_CONFIG_HOME`) and never leaves your machine.

### Optional: show the line inside Claude Code (opt-in hook)

When your agent runs the CLI through Claude Code's Bash tool, the output is not a terminal, so the line above stays silent: the model never sees an ask and never repeats one. At a value moment the CLI prints a neutral marker instead, with no money in it:

```
[value moment] chapter-passed key=3f1c... words=2412 | Chapter 3 passed all 3 checks ✓.
```

If you want the line to reach you there too, turn on the hook `scripts/fund_line_hook.py`. It runs after each Bash call, spots that marker in `ghostwriter.py` output, and shows the line to **you** as a Claude Code `systemMessage`, which is not handed to the model as an instruction. It is **off by default**: nothing installs it, and this repo's own `.claude/settings.json` does not enable it. To turn it on, add this to `.claude/settings.local.json` in your clone (personal and git-ignored; Claude Code merges it with the repo's boundary hooks) or to `~/.claude/settings.json`:

```json
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Bash",
        "hooks": [
          { "type": "command", "command": "python3 \"$CLAUDE_PROJECT_DIR/scripts/fund_line_hook.py\"" }
        ]
      }
    ]
  }
}
```

The hook uses the CLI's own state file and rules, so one set of caps covers both: the moments declared in `FUNDING-STATUS.json` (each has a `hook_match`), the first one then about every 10th, never more than once a week, each outcome counted once. It is silent in CI, with `GHOSTWRITER_NO_FUND=1`, after `python3 scripts/ghostwriter.py fund --off` (one switch for both), and for good once the build cost is covered. Any error, and it exits quietly; it never blocks a tool call. To turn it off again, delete the snippet.

## License

Two licenses, split by what the file is:

- **Code: [MIT](LICENSE).** `scripts/`, `tests/`, `.claude/hooks/` and `.claude/settings.json`.
- **Content: [CC BY 4.0](LICENSE-CONTENT).** `prompts/`, the docs (`README.md`, `AGENT.md`, `CLAUDE.md`, `PRFAQ.md` and other Markdown), `book-template/`, `examples/` and `data/`. Use and adapt them for anything, commercial included; credit "Ghost Writer by Laurence Wong" with a link to this repo, and say if you changed them.

Books you write with Ghost Writer are yours. Neither license reaches your own book workspace.

---
<sub>Built with Claude Code (~12M Claude tokens so far; see `FUNDING-STATUS.json`). If it saved you time, you can help cover the tokens: [Sponsor](https://github.com/sponsors/laurencewong).</sub>
