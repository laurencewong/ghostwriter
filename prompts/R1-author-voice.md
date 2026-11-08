# Research stage R1: capture the author's own words, verbatim

The author's quotes, metaphors and analogies are the spine of the book. Agents paraphrase by
reflex and lose them. Do not paraphrase. Log them the moment the author says them, word for word:

    python3 scripts/ghostwriter.py voice-log <book> "exact words" --kind quote|metaphor|analogy|belief|correction|story \
        --context "what prompted it" [--chapter ch03]

- Copy the words exactly, typos aside. Never tidy the grammar or "improve" a metaphor.
- Log corrections too ("we are in the research phase, not the writing phase"). They are the
  author's judgment about the work, and they set the pace.
- An analogy the author offers ("X is like Y") gets a research note of its own
  (`prompts/R4-analogy-gap-fill.md`).
- Tag an entry with `--chapter` once it clearly belongs to a chapter. That chapter's drafts must
  then carry it verbatim.
- Stories from the author are logged here and, when they carry facts, filed as interview sources
  too (`interview-file`), so a chapter can cite them.

**In drafts:** list the entries a chapter builds on in front matter (`author_voice: V002, V005`)
and build the passage around the author's exact words. You may quote, frame and answer them.
You may not reword them. `check-author-voice` fails a draft where a listed or chapter-tagged entry
no longer appears word for word. In prose, tag the sentence that carries one with `[V###]`.
