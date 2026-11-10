#!/usr/bin/env python3
"""fund_line_hook.py: OPT-IN Claude Code hook that shows YOU (not the model) Ghost Writer's one-line
support note at a declared value moment.

Why it exists: when your agent runs `ghostwriter.py` through Claude Code's Bash tool, stdout is not a
terminal, so the CLI's own line stays silent (on purpose: the model must never see or repeat an ask).
At a value moment the CLI prints a neutral marker instead, with no money in it:

  [value moment] chapter-passed key=<hash> words=2412 | Chapter 3 passed all 3 checks ✓.

This hook runs after each Bash tool call, spots that marker in ghostwriter.py's output, and prints
{"systemMessage": "<the line>"}. Claude Code shows a systemMessage to the user; it is not handed to
the model as an instruction.

Nothing installs it and it is off by default. To turn it on, add to `.claude/settings.local.json`
(personal, git-ignored) or `~/.claude/settings.json`:

  {"hooks": {"PostToolUse": [{"matcher": "Bash", "hooks": [{"type": "command",
     "command": "python3 \\"$CLAUDE_PROJECT_DIR/scripts/fund_line_hook.py\\""}]}]}}

Same rules as the CLI line, and the same state file (so one set of caps covers both):
  - only at a value moment declared in FUNDING-STATUS.json (value_moments[].hook_match)
  - the first moment, then about every 10th, at most once per 7 days; each outcome counts once
  - silent in CI, with GHOSTWRITER_NO_FUND=1, after `ghostwriter.py fund --off` (or this script's
    --off), and for good once the build cost is covered
  - state lives in $XDG_CONFIG_HOME/ghostwriter/fund.json and never leaves your machine
  - any error: exit 0 silently. A support line must never break a tool call.
Standard library only. Based on the pick-donation-moment hook template.
"""
from __future__ import annotations

import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ghostwriter as gw  # noqa: E402  (same caps, line and state as the CLI)


def silenced() -> bool:
    """CI and env opt-out. No TTY check here: a hook never has a terminal."""
    for v in ("GHOSTWRITER_NO_FUND", "FUND_NO_FUND"):
        if os.environ.get(v, "").strip() not in ("", "0"):
            return True
    return any(os.environ.get(v, "").strip() not in ("", "0", "false") for v in gw.CI_VARS)


def tool_output(event: dict) -> str:
    resp = event.get("tool_response") or {}
    if isinstance(resp, dict):
        return str(resp.get("stdout", "")) + "\n" + str(resp.get("output", ""))
    return str(resp)


def handle(event: dict, fs: dict | None = None, now: datetime | None = None) -> str | None:
    """Return the line to show for this PostToolUse event, or None. Updates the shared fund state."""
    if silenced() or event.get("tool_name", "Bash") != "Bash":
        return None
    fs = gw.load_funding_status() if fs is None else fs
    if not fs or gw.fund_covered(fs):
        return None
    cmd = str((event.get("tool_input") or {}).get("command", ""))
    out = tool_output(event)
    if gw.VALUE_MOMENT_MARKER not in out:
        return None
    for m in fs.get("value_moments", []):
        hm = m.get("hook_match") if isinstance(m, dict) else None
        if not hm or not re.search(hm.get("command", r"(?!)"), cmd):
            continue
        mm = re.search(hm.get("output", r"(?!)"), out, re.M)
        if not mm:
            continue
        g = mm.groupdict()
        words = int(g["words"]) if (g.get("words") or "").isdigit() else None
        prefix = (g.get("prefix") or hm.get("prefix") or "").strip()
        key = g.get("key") or ""
        if not key:
            return None
        return gw.fund_count(m["id"], key, prefix, fs, now=now, words=words)
    return None


def main(argv: list[str]) -> int:
    if argv and argv[0] in ("--off", "--on"):
        st = gw.load_fund_state()
        st["off"] = argv[0] == "--off"
        gw.save_fund_state(st)
        print("Ghost Writer support line " + ("off (CLI and hook)." if st["off"] else "on."))
        return 0
    try:
        event = json.load(sys.stdin)
    except ValueError:
        return 0
    line = handle(event) if isinstance(event, dict) else None
    if line:
        print(json.dumps({"systemMessage": line}))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:]))
    except Exception:  # noqa: BLE001 - a support line must never break a tool call
        sys.exit(0)
