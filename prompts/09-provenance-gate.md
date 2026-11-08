# Stage 8b: fact and provenance gate

    python3 scripts/ghostwriter.py check-provenance <book> drafts/chNN/run-K.md

The script flags sentences that look factual (numbers, studies, surveys, generalizations)
and carry no `[S###]`, `[opinion]`, `[author]` or `[V###]` tag, any cited ID that is not
registered, any cited source still marked `confirm-before-print`, and any `[CBP]` marker.
Secondhand sources and sources with no recorded status pass with a warning.

Then, in a fresh context, check what the script cannot:
1. For each `[S###]`, open the source. Does it actually say that? Same number, same scope,
   same date? If not, fix the sentence or the citation. If you checked it, record how:
   `cite-status <book> S### --status verified --how "..."` (`prompts/R7-citation-honesty.md`).
2. Find factual claims the regex missed (no digits, still a fact: "the company was founded
   by engineers"). Tag them.
3. `[opinion]` must be an opinion, not a fact dodging a citation. If it could be checked, it
   needs a source.
4. Write the result at the bottom of the draft as an HTML comment:
   `<!-- provenance: N claims, N cited, N opinion, checked YYYY-MM-DD -->`
