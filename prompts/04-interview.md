# Stage 4: interview the author

**Read:** `spine.md` (Gaps section), `thesis.md`, existing `interview/questions.md`.
**Write:** new lines in `interview/questions.md`, format `- [ ] Q###  question text`.

Good questions pull out what only the author knows: a scene, a number they measured, a
decision they made and why, a time they were wrong.

- Ask for stories, not opinions: "Tell me about the time..." beats "Do you think...".
- One question per line. Under 30 words. No compound questions.
- Tag each with the chapter it feeds: `(ch03)`.
- Include at least one question per `tests` chapter that invites the author to argue
  against themself: "What is the best evidence you have seen that this is wrong?"
- Max 7 new questions per round. The author answers in batches.

Filing answers is deterministic:

    python3 scripts/ghostwriter.py interview-open <book>
    python3 scripts/ghostwriter.py interview-file <book> Q004 --answer-file a.txt

Each answer becomes a source a chapter can cite as `[S###]`.
