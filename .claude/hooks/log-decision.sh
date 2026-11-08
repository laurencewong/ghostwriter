#!/usr/bin/env bash
# log-decision.sh: Ghost Writer's PostToolUse audit hook. Appends one line per consequential
# action (writes, non-read shell commands) to decisions-log.md, which is git-ignored so a
# personal audit trail never lands in a public history. In fleet mode it defers to the
# fleet's canonical logger. Best effort: never fails the tool call.
set -uo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
[ -r "$HERE/fleet.local.sh" ] && . "$HERE/fleet.local.sh"
export AGENT_NAME="ghostwriter"
export AGENT_VAULT="${GHOSTWRITER_VAULT:-$(cd "$HERE/../.." && pwd)}"
if [ -n "${FLEET_LIB:-}" ] && [ -r "$FLEET_LIB/log-decision.sh" ]; then
  . "$FLEET_LIB/log-decision.sh"
  exit 0
fi
command -v jq >/dev/null 2>&1 || exit 0
INPUT="$(cat)"
tool="$(printf '%s' "$INPUT" | jq -r '.tool_name // ""')"
case "$tool" in
  Write|Edit|MultiEdit|NotebookEdit) what="$tool $(printf '%s' "$INPUT" | jq -r '.tool_input.file_path // "?"')" ;;
  Bash)
    cmd="$(printf '%s' "$INPUT" | jq -r '.tool_input.command // ""' | head -1 | cut -c1-200)"
    case "$(printf '%s' "$cmd" | awk '{print $1}')" in ls|cat|grep|rg|find|head|tail|wc|echo|pwd|jq) exit 0;; esac
    what="Bash $cmd" ;;
  *) exit 0 ;;
esac
printf -- '- %s  %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$what" >> "$AGENT_VAULT/decisions-log.md" 2>/dev/null || true
exit 0
