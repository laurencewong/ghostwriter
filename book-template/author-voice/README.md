# author-voice

The author's own words, verbatim and timestamped: quotes, metaphors, analogies, beliefs,
corrections, stories. They are the spine of the book. Log them the moment the author says them:

    python3 scripts/ghostwriter.py voice-log <book> "the exact words" --kind metaphor --context "what prompted it"

`log.jsonl` is the record; `log.md` is generated from it. A draft that builds on an entry lists
it in front matter (`author_voice: V003, V007`) and keeps it word for word. Entries logged with
`--chapter ch03` are required in that chapter. `check-author-voice` (and `tournament`/`promote`)
fail a draft that paraphrased them away.
