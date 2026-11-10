# PR/FAQ: Ghost Writer
*Draft 2026-11-08, revised for v0.3 (research first) · status: draft (not approved; the repo stays private until the maintainer says publish)*

## Press release
**Headline:** Ghost Writer: write your nonfiction book with AI, with every fact sourced and the voice still yours.
**Subhead:** An open-source agent for authors with an idea and a body of published writing. It researches before it writes, keeps the author's own words verbatim, and turns both into chapters which cite their sources, sound like the author, and argue honestly.

**ONLINE, on publish (date to be set).** Ghost Writer is a free, open-source ghostwriting agent for nonfiction authors who already write in public: newsletter writers, bloggers, practitioners with years of posts. It runs inside Claude Code. You bring a thesis and your own writing; it brings a research desk, an interviewer, and an editor who refuses to make things up.

**The problem.** Writers who try to turn their ideas into a book with AI hit the same walls. The tool skips the research and starts writing chapters on day one. The model invents facts that sound right. The prose comes out in the flat, generic voice everyone now recognizes. And the book turns into a pamphlet: chapter after chapter restating the thesis, never testing it. The author's best lines get paraphrased into mush. Fixing all of it by hand takes longer than writing without AI.

**The solution.** Ghost Writer starts every book in a research phase with exit criteria the author writes, and it will not draft chapters until the author moves the book on. Research has structure: how other worlds solved the same problem, a coverage grid that answers "did we miss anything?" with a score, the author's analogies tested for where they break, the famous findings rated holds / contested / misread, and a theory whose every proposition names what would prove it wrong. Every citation says whether it was verified, and how. Then Ghost Writer puts gates where AI writing fails. A chapter cannot be promoted until every factual sentence cites a registered source or is tagged as the author's opinion, until it clears a stock-phrase check, until it contains a steelmanned objection and an honest verdict on what happened to the thesis, and until the author's own logged words appear in it word for word. The one thing it does better than anything else: **it would rather leave a marked gap than fill it with something plausible.**

> "Draft quote for the maintainer's edit: I had a thesis and five hundred posts, and every AI tool I tried wanted to write a different book. I built the one that argues with me."

**How it works.** Initialize a book workspace and point it at your own writing (five minutes). The book starts in research: a plan, a working hypothesis (which can change, with the old one archived and the reason kept), and research notes, while every quote and metaphor you say is logged verbatim. When your exit criteria are met, you move the book to synthesis. The agent proposes thesis options and you pick one. It builds the chapter spine, interviews you to fill evidence gaps, and files your answers as sources. Then for each chapter it writes several independent drafts, runs every gate, judges the survivors head to head, and promotes the winner with revision notes.

> "Hypothetical user quote: The provenance gate flagged a statistic I'd been repeating in talks for years. I couldn't find where it came from either. That chapter got better when I cut it."

**Get started.** Clone the repo, run `python3 scripts/ghostwriter.py init books/my-book`, and open `examples/demo-book/` to see a finished run.

## External FAQ (what a user asks)
1. **Who is this for, and who is it not for?** Nonfiction authors with a point of view and some published writing to learn a voice from. Not for fiction, not for people who want a book with no writing of their own, and not for imitating another author.
2. **What does it cost, and what does it need?** The code is free. It needs Python 3.9+, `jq`, and an AI coding agent (built for Claude Code), which has its own subscription or API cost.
3. **Where does my data go? Who can see it?** Your files stay in your book workspace. The script makes no network calls. Your AI agent sends what it reads to its model provider under that provider's terms. Sensitive sources can be registered by pointer without copying.
4. **How long does setup take?** About five minutes to a first `status`. A first gated chapter takes an afternoon, most of it answering interview questions.
5. **What doesn't it do?** It does not verify that a source actually says what a sentence claims (that check is a prompt and, finally, you). It does not format for print or publish anything. English only. The voice profile is a set of measurements, so drafts still need your edit.
6. **How is this different from asking a chatbot to write my book?** A chatbot optimizes for fluent text. Ghost Writer optimizes for a book you can defend: sources by ID, your voice measured from your own work, a required case against your thesis, and drafts that compete instead of one take.
7. **Why won't it write a chapter on day one?** Because the first real run showed what happens when it does: the author spent the session pulling the tool back to research. A new book starts in the research phase. You can override any time; the override is logged, so you can see later that you chose it.
8. **What happens if it breaks or I stop using it?** Everything is plain Markdown and JSON in your workspace. Nothing is locked in a format or a service.

## Internal FAQ (what we ask ourselves)
1. **Why build instead of buy?** AI book tools exist, but the ones we found optimize for word count and speed. None enforce source IDs per claim or a required steelman per chapter. The gates are the product, and they are small enough to build.
2. **What's the smallest version that proves it?** The CLI with three gates, the prompts, and one fictional demo chapter that passes while a sibling draft visibly fails. That is what v0.1 shipped. v0.3 adds the research phase, because the first real author needed research before chapters. No web UI, no scheduler, no publishing.
3. **Does it serve the maintainer's public work?** Yes: it is the tool behind the maintainer's own book project, and it shows the build-in-public approach to AI work (how agents are bounded, gated and checked).
4. **Boundary check.** Tracked files contain no personal data, secrets, employer content, partner names, or family. The demo is fictional and labeled so in every source. The maintainer's real book lives in a separate private directory that is never part of this repo. Scan run 2026-11-08: clean (see the build notes).
5. **Maintenance.** We will fix bugs in the gates and keep the prompts current. We do not promise support for other agents, other languages, or feature requests.
6. **Success at 30/90 days.** 30 days: 50 stars and 3 outside users who report a gated chapter (issue or post). 90 days: 150 stars, 10 forks, and the maintainer's own book with 3 chapters through every gate.
7. **Risks.** Legal: the no-imitation rule and short-quote rule reduce copyright exposure; code is MIT and prompts/docs are CC BY 4.0. Trust: a tool named "ghost writer" invites the concern that it hides AI use, so the README states the AI-tell gate is for quality and disclosure is the author's call. Support burden: low, the code is small and has no dependencies.
8. **Kill or keep.** At 90 days, under 25 stars and no outside user reporting a chapter: archive it and keep using it privately.
9. **Tokens and "cover the tokens".** Build token count goes in the ledger before publish; the README footer carries the count and a Sponsor link. Optional, never paywalled; the code stays free.

---
Voice and brand review: pending.
