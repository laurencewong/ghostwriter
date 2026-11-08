# Stage 1: thesis options

**Read:** everything in `input/thesis/` (including `working-hypothesis.md` and the `archive/` of
superseded options and their reasons), `author-voice/log.md`, the research notes in `research/`,
`voice/profile.md` if present, and `sources/index.json`.
**Write:** `input/thesis/options.md`.

**Phase check first:** `python3 scripts/ghostwriter.py phase status <book>`. This stage belongs to
synthesis. In the research phase, options are fine if the author asks, but label every one
"working hypothesis" and do not recommend a pick; the research is not done.

1. Collect every candidate thesis already in `input/thesis/`. Keep the author's wording, and build
   each statement around the author's own words from `author-voice/` where they fit (cite `V###`).
   Do not re-propose an archived option unless new evidence answers the reason it was dropped.
2. Add up to three more only if the inputs clearly point at them. Label them `(new)`.
3. For each option, write:
   - **Statement:** one sentence, arguable. If no smart person would disagree, it is a topic, not a thesis.
   - **Who disagrees, and their best argument** (two sentences).
   - **Evidence on hand:** source IDs that already support it, or "none yet".
   - **Evidence needed:** what would have to be true; what would prove it wrong.
   - **Book test:** can it carry 8 to 12 chapters without repeating itself? yes / thin / no.
   - **Author fit:** does the author have lived experience or data here nobody else has?
4. Score each 1 to 5 on: arguable, evidenced, book-sized, author-only. Show the table.
5. End with a recommendation and the one question the author should answer before picking.
Do not pick. Picking is stage 2, and it is the author's call.
