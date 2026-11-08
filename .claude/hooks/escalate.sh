#!/usr/bin/env bash
# escalate.sh: Ghost Writer's PreToolUse boundary hook.
#
# Two modes, never fail open:
#   1. Fleet mode: if a fleet boundary library is configured (FLEET_LIB, usually set in the
#      git-ignored .claude/hooks/fleet.local.sh), source its escalate.base.sh. That base carries
#      the boundary-v2 shim and reads FB_AGENT from AGENT_NAME below.
#   2. Standalone mode (anyone who clones this repo): source the bundled boundary-lite.sh.
# If neither can be loaded, deny everything.
set -uo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Optional, git-ignored, machine-specific config (FLEET_LIB, GHOSTWRITER_EXTRA_ROOTS).
[ -r "$HERE/fleet.local.sh" ] && . "$HERE/fleet.local.sh"

export AGENT_NAME="ghostwriter"                     # FB_AGENT id for the fleet base
export AGENT_VAULT="${GHOSTWRITER_VAULT:-$(cd "$HERE/../.." && pwd)}"
# Extra absolute roots the agent may write to (book workspaces outside this repo), colon-separated.
export FLEET_EXTRA_WRITE_ROOTS="${GHOSTWRITER_EXTRA_ROOTS:-}"
export FLEET_LAUNCHAGENT_PREFIX=""                  # no scheduler/persistence writes, ever

deny_all() {
  printf '{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"deny","permissionDecisionReason":"%s"}}\n' "$1"
  exit 0
}

if [ -n "${FLEET_LIB:-}" ]; then
  [ -r "$FLEET_LIB/escalate.base.sh" ] || deny_all "FLEET_LIB set but escalate.base.sh not found; failing closed"
  . "$FLEET_LIB/escalate.base.sh"
elif [ -r "$HERE/boundary-lite.sh" ]; then
  . "$HERE/boundary-lite.sh"
else
  deny_all "no boundary logic found; failing closed"
fi
