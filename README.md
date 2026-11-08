# Ghost Writer

An AI ghostwriting agent for nonfiction authors: it turns your thesis, your interview answers and your own published writing into book chapters where every fact has a source, the voice is yours, and the thesis gets tested instead of just sold.

It runs inside an AI coding agent (built for Claude Code). The judgment steps are plain-text prompts. The steps that should never be left to a model's judgment (the source registry, the voice measurements, and the gates a chapter must pass) are a small Python script with no dependencies.

## Quickstart

Needs Python 3.9+, `jq` (for the boundary hook), and Claude Code or a similar agent. Setup takes about five minutes.

```sh
git clone <this repo> ghostwriter && cd ghostwriter
python3 scripts/ghostwriter.py init books/my-book --title "Working title" --author "Your Name"
# put a few of your own published pieces in books/my-book/voice/samples/
python3 scripts/ghostwriter.py voice-build books/my-book
python3 scripts/ghostwriter.py status books/my-book
```

Then open the repo in Claude Code and say: "Run stage 1 on books/my-book" (see `prompts/00-README.md` for every stage). To see a finished run first, look at `examples/demo-book/`, a complete fictional example.

## How it works

1. **Thesis.** You drop candidate ideas in `input/thesis/`. The agent lays out the options, who would disagree with each, and what evidence each needs. **You pick.**
2. **Spine.** The thesis becomes 8 to 12 chapters. Every chapter is labeled `advances`, `tests` or `complicates` the thesis. At least one in four must test or complicate it.
3. **Interview loop.** Gaps in the evidence become interview questions for you. Your answers are filed as sources the chapters can cite.
4. **Sources.** Posts, notes, datasets, articles: each gets an ID (`S001`, `S002`, ...). Private material can be registered by pointer, without copying it.
5. **Voice.** `voice-build` measures your rhythm and habits (sentence length, questions, contractions, signature phrases) from **your own writing only**. It refuses samples not marked as yours.
6. **Chapters, multi-run.** The agent writes K independent drafts, each from a different opening angle. Every draft goes through three gates:
   - **AI-tell gate:** stock machine phrasing fails the draft.
   - **Fact and provenance gate:** every sentence that looks factual must cite a source ID or be tagged `[opinion]` / `[author]`. Unknown IDs and `[NEEDS SOURCE]` markers fail.
   - **Keep-the-thesis-honest gate:** the chapter needs a stated role and claim, a steelmanned objection section (60+ words), and a closing verdict on what happened to the thesis.

   Drafts that pass every gate go to a head-to-head tournament. The winner absorbs the best idea from each loser and is promoted. `promote` refuses any draft that fails a gate.
7. **Revision notes.** What the chapter now proves, open evidence gaps, and a Decision block whenever the evidence pushes against the thesis.

```
thesis -> spine -> interview <-> sources -> voice
                                   |
            K drafts -> gates (AI-tell, provenance, thesis) -> tournament -> promote -> revision notes
```

## Limitations

- **It does not write your book for you.** Your lived experience comes from your interview answers. Where it has no source, it leaves a marker instead of inventing one.
- **The gates are tripwires, not truth.** The provenance gate finds sentences that look factual and checks that they carry a tag. It cannot tell whether a source actually says what the sentence claims. That is a prompt-driven check (`prompts/09`) and, in the end, yours.
- **Voice is measured, not cloned.** The profile is a handful of numbers and habits. Drafts will still need your edit to sound like you.
- **English only.** The sentence splitter and phrase list assume English prose.
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

## License

Not chosen yet. See [LICENSE](LICENSE). Until it is, no license is granted.

---
<sub>Built with Claude Code (token count pending the build ledger). If it saved you time, you can help cover the tokens: see the Sponsor button.</sub>
