# voice

`samples/` (or the paths listed under `voice.samples` in ghostwriter.json) hold the author's
OWN published writing. Every sample entry must say `"owner": "self"`; `voice-build` refuses
anything else. Ghost Writer never learns a voice from another writer.

    python3 scripts/ghostwriter.py voice-build <book>

writes `profile.md` and `profile.json` here.
