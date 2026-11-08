# Research stage R7: citation honesty, and research into sources

Every citation carries a status. The status says what was actually checked.

| status | means | needs |
|---|---|---|
| `verified` | you saw the claim in the source itself | **how**: fetched the source, PubMed record, Crossref/DOI metadata, book in hand, recomputed the data |
| `confirm-before-print` | from memory, a summary, or a search snippet; plausible, not checked | nothing yet, but it cannot appear in a chapter |
| `secondhand` | you saw it cited by another source, not the original | **via**: the source that cites it |

**In research notes:** every note ends with a `## Sources` table
(`| key | citation | url | status | how |`). `confirm-before-print` is fine here. Mark the claim
itself too, so it is not forgotten. Never upgrade a status you did not check.

**In chapter drafts:** the provenance gate (`check-provenance`, `tournament`, `promote`) fails a
draft that cites a `confirm-before-print` source, or carries a `[CBP]` / `[confirm before print]`
marker. Secondhand sources pass, with a warning. Fix it by checking the source, then:

    python3 scripts/ghostwriter.py cite-status <book> S012 --status verified --how "fetched the PDF, p. 7"

**When web search is rate-limited or exhausted,** do not fall back to memory and call it checked.
Fetch primary sources directly instead: the DOI resolver, the journal's page, PubMed or Europe PMC
records, Crossref metadata, a publisher's catalog page, the dataset's own page. Note in the
`how` column which route you used. If you cannot reach a source at all, it stays
`confirm-before-print`, and you say so in the note.

**Research into sources.** When the book reaches synthesis, register the research so chapters can
cite it by ID:

    python3 scripts/ghostwriter.py ingest-research <book> research/<note>.md

Each Sources row becomes a source (`S###`) that keeps its status and remembers which note it came
from. Running it again skips rows already registered (`research/source-map.json`).
