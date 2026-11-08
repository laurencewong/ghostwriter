# Stage 5: ingest sources

Every fact in the book traces to a registered source. Register with:

    python3 scripts/ghostwriter.py add-source <book> <file-or-url> --kind post|note|dataset|article|interview|book|talk --title "..." --date YYYY-MM-DD

Use `--pointer` when the content must stay where it is (private files, big datasets): the
registry records the path, not a copy.

After registering, open `sources/S###.md` and add under the content:
- **Claims this supports:** short bullets, each one a claim a chapter might make.
- **Exact passages:** the lines you would cite, each 40 words or fewer, with location
  (page, timestamp, row).
- **Reliability:** primary or secondary; who made it; what they might be wrong about.

For datasets: record the file, the query or filter, and the resulting number, so anyone
can recompute it. A number with no recipe is not a source.

For other people's work: summarize, never paste long passages. Quotes stay short and credited.
