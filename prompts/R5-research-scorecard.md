# Research stage R5: popular-research scorecard

Readers arrive having met the famous findings in the topic: from talks, airport books, social
posts. Giving each one its honest current status is a credibility edge. A reader who learns here
what a famous study actually found will trust the rest of the book.

    python3 scripts/ghostwriter.py scaffold <book> scorecard --name "famous findings, rated"

1. List 8 to 15 findings as they are popularly told, in the `## Scorecard` table.
2. For each, find the original source and the best later evidence (replications, meta-analyses,
   registered reports, the original authors' own corrections).
3. **Status** is one word first: **HOLDS**, **CONTESTED** or **MISREAD**, then a short reason.
   MISREAD means the finding is fine but the popular version says something it did not.
4. **Replication:** what is known: replicated at scale, failed a registered replication, never
   replicated, or the original authors walked it back.
5. Fill `## Foils`: the overhyped findings the book will use as foils, and how ("here is what the
   study actually found"). Fill `## Pattern`: what separates findings that held from ones that did not.
6. Statuses in the Sources table follow `R7`. Exact effect sizes that you have not checked against
   the paper are `confirm-before-print`.

Run `check-research` on the note. Never call a finding debunked on the strength of one critic.
