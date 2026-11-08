# Changelog

## 0.2.0 (unreleased)
- The value-moment line now leads with the value, as a labeled estimate: "That's about N hours of
  drafting you didn't do". Words in the passing chapter (or, for a full draft, every promoted chapter)
  ÷ a cited composing-speed benchmark (Karat et al. 1999, ~1,140 words/hour), claimed at 50% and
  rounded down; no value claim under 10 minutes. Assumptions live in `FUNDING-STATUS.json`
  (`value_estimates`), capped at a 50% claim share in code.
- `fund` prints the estimate's formula, benchmark source, why it is conservative, a worked example and
  the math for your own last chapter.
- Shorter ask: "Ghost Writer is free; building it cost ~$X in AI, $Y covered. Chip in $3: <link>".

## 0.1.0
- First version: thesis, spine, interview loop, source registry, voice profile, multi-run
  chapter drafts with AI-tell, provenance and thesis-honesty gates, tournament, promote,
  revision notes.
- Fictional demo book in `examples/demo-book/`.
- Standalone boundary hook with tests.
- `fund` command and an occasional one-line sponsor note at declared value moments (a chapter's
  first pass of all three gates; a complete draft). Capped, opt-out, silent in CI and when piped,
  stops once the build cost is covered, and never written by the model.
