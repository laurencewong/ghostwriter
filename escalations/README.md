# escalations/

Decisions handed to the author, one file each, append-only. Format:

- **Decision**: one line, the call to be made.
- **Options**: the real alternatives.
- **Recommendation**: the pick, and why.
- **What unblocks**: exactly what is needed (a yes or no, a source, a choice).

Mark resolved entries `status: resolved: <call> (date)`. The boundary hook also appends blocked
actions to `boundary-denials.md` here. Everything in this folder except this README is
git-ignored.
