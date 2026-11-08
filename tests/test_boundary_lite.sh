#!/usr/bin/env bash
# Boundary test for the standalone hook (.claude/hooks/escalate.sh in standalone mode).
# Runs against a throwaway workspace; never touches the real escalations/. Needs jq.
set -uo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
HOOK="$HERE/../.claude/hooks/escalate.sh"
TMPV="$(mktemp -d)"; EXTRA="$(mktemp -d)"; OUTSIDE="$(mktemp -d)"
trap 'rm -rf "$TMPV" "$EXTRA" "$OUTSIDE"' EXIT
mkdir -p "$TMPV/.claude/hooks"
cp "$HERE/../.claude/hooks/escalate.sh" "$HERE/../.claude/hooks/boundary-lite.sh" "$TMPV/.claude/hooks/"
HOOK="$TMPV/.claude/hooks/escalate.sh"     # copy without fleet.local.sh = standalone mode
export GHOSTWRITER_VAULT="$TMPV" GHOSTWRITER_EXTRA_ROOTS="$EXTRA"
unset FLEET_LIB

pass=0; fail=0
j() { jq -nc --arg t "$1" --argjson ti "$2" '{tool_name:$t, tool_input:$ti}'; }
run() { # run allow|deny "desc" json
  local got
  got="$(printf '%s' "$3" | env -u FLEET_LIB bash "$HOOK" 2>/dev/null | jq -r '.hookSpecificOutput.permissionDecision // "ERROR"')"
  if [ "$got" = "$1" ]; then pass=$((pass+1)); echo "  ok   [$1] $2"
  else fail=$((fail+1)); echo "  FAIL expected=$1 got=$got  $2"; fi
}
w() { j Write "$(jq -nc --arg p "$1" '{file_path:$p, content:"x"}')"; }
b() { j Bash "$(jq -nc --arg c "$1" '{command:$c}')"; }

echo "boundary-lite suite -> $HOOK"
run allow "Read anywhere"                      "$(j Read "$(jq -nc --arg p "$OUTSIDE/a.md" '{file_path:$p}')")"
run allow "WebSearch"                          "$(j WebSearch '{"query":"x"}')"
run allow "write inside workspace"             "$(w "$TMPV/drafts/ch01/run-1.md")"
run allow "write inside extra root"            "$(w "$EXTRA/book/thesis.md")"
run deny  "write outside workspace"            "$(w "$OUTSIDE/x.md")"
run deny  "write with ../ escape"              "$(w "$TMPV/../escape.md")"
run deny  "write with no path"                 "$(j Write '{"content":"x"}')"
run allow "run the CLI"                        "$(b "python3 scripts/ghostwriter.py status examples/demo-book")"
run allow "git commit locally"                 "$(b "git add -A && git commit -m wip")"
run deny  "git push"                           "$(b "git push origin main")"
run deny  "chained git push"                   "$(b "git commit -m x && git push")"
run deny  "gh repo create"                     "$(b "gh repo create me/book --public")"
run deny  "gh release"                         "$(b "gh release create v1")"
run deny  "npm publish"                        "$(b "npm publish")"
run deny  "curl POST"                          "$(b "curl -X POST https://api.example.com/post -d hi")"
run allow "curl GET"                           "$(b "curl -s https://example.com/page")"
run deny  "rm -rf"                             "$(b "rm -rf drafts")"
run deny  "git reset --hard"                   "$(b "git reset --hard HEAD~1")"
run deny  "launchctl"                          "$(b "launchctl load ~/Library/LaunchAgents/x.plist")"
run deny  "crontab"                            "$(b "crontab -e")"
run deny  "osascript send"                     "$(b "osascript -e 'tell app \"Messages\" to send'")"
run deny  "redirect outside workspace"         "$(b "echo hi > /opt/gw-outside/x.txt")"
run allow "redirect inside workspace"          "$(b "echo hi > $TMPV/x.txt")"
run allow "redirect to /tmp"                   "$(b "echo hi > /tmp/gw-test.txt")"
run deny  "cp outside workspace"               "$(b "cp a.md /opt/gw-outside/a.md")"
run deny  "MCP send"                           "$(j mcp__chat__send_message '{}')"
run deny  "MCP publish"                        "$(j mcp__blog__publish_post '{}')"
run allow "MCP read"                           "$(j mcp__docs__read '{}')"
echo "RESULT: $pass passed, $fail failed"
[ "$fail" = 0 ]
