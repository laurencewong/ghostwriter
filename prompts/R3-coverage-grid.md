# Research stage R3: coverage grid ("are we MECE?")

Authors ask "how confident are we that we have everything?" Answer with a grid you can score,
not a feeling.

    python3 scripts/ghostwriter.py scaffold <book> coverage --name "mechanisms x situations"
    python3 scripts/ghostwriter.py coverage <book>

**Write:** `research/coverage/<name>.json` (the script writes `<name>.report.md` next to it).

1. **Mechanism key** (`mechanisms`): 6 to 15 codes, each with a definition, what it includes and
   what it excludes (and where that goes). Every item maps to **exactly one** mechanism. Write
   tie-breaker rules (`tie_breakers`): split bundled practices into parts; classify by the active
   ingredient ("what stops working if you remove it?"); a fixed precedence order for ties.
   Cross-walk established frameworks into the key until nothing is left over.
2. **Situation list** (`situations`): grounded in an established framework from the field, named
   with its citation in `framework`. Not invented categories.
3. **Cells** (`cells`): one per situation x mechanism. Status is `filled` (with the practice, the
   domain it came from, and an evidence grade), `dup` (with `dup_of`), `empty` (with `priority`
   and `why`, when it matters and nothing credible exists), or `na` (the mechanism does not apply).
   Missing cells count as unassessed, not filled.
4. **Items** (`items`): every named practice from the borrow scan, with its domain, its one
   mechanism, an evidence grade (or `none`), and source keys.
5. Run `coverage`. Read the report honestly: "filled" means a credible borrowed practice exists,
   not that it is proven for this audience. Fix every listed problem, merge the duplicates it
   flags, and keep the "no evidence" list visible.

**Breadth mode.** An author may relax MECE in favor of breadth ("full coverage of the major kinds
of groups"). Then set `"mode": "breadth"`, list `domains` (each `required: true` or not), and the
score becomes the share of required domains with at least `min_practices_per_domain` evidenced
items. Keep the grid as a secondary view if it helps.

**Next:** the top-ranked empty cells become research tasks, often filled by the author's analogies
(`R4`). The phase's coverage threshold lives in `ghostwriter.json` under `research`.
