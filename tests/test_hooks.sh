#!/usr/bin/env bash
# tests/test_hooks.sh: Ghost Writer's boundary test.
# Always runs the standalone suite. If a fleet boundary library is configured (FLEET_LIB, or
# the git-ignored .claude/hooks/fleet.local.sh), also runs that library's shared suite,
# because in fleet mode escalate.sh sources the fleet base. Exits non-zero on any failure.
set -uo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
rc=0
bash "$HERE/test_boundary_lite.sh" || rc=1
LOCAL="$HERE/../.claude/hooks/fleet.local.sh"
[ -z "${FLEET_LIB:-}" ] && [ -r "$LOCAL" ] && . "$LOCAL"
if [ -n "${FLEET_LIB:-}" ] && [ -r "$FLEET_LIB/test_hooks.sh" ]; then
  echo "fleet mode: running the shared suite in $FLEET_LIB"
  bash "$FLEET_LIB/test_hooks.sh" || rc=1
fi
exit $rc
