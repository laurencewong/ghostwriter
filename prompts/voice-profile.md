# Voice profile

The voice is learned only from the author's own published writing.

1. List the samples in `ghostwriter.json` under `voice.samples`, each with `"owner": "self"`.
   Prefer published pieces over drafts; give drafts a lower `weight`.
2. Run `python3 scripts/ghostwriter.py voice-build <book>`. It writes the numbers.
3. Read 5 to 10 samples and append **Judgment notes** to `voice/profile.md`: how the author
   opens, how they handle evidence, what they never do, words they overuse. Describe; do not
   copy sentences.

Never write "in the style of" anyone. Never use another writer's text as a sample, even as a
reference point. If the author asks to sound like a famous writer, note it as a decision for
them and explain why the tool does not do it: it produces pastiche and invites a copyright problem.
