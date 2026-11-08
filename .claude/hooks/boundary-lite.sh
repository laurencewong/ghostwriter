#!/usr/bin/env bash
# boundary-lite.sh: the standalone boundary for Ghost Writer (sourced by escalate.sh).
#
# Posture: allow by default, deny the outward and the irreversible. A PreToolUse hook sees
# only the tool name and its input, so this is a tripwire, not a sandbox. Needs jq.
#   - writes only inside the repo and FLEET_EXTRA_WRITE_ROOTS
#   - no publishing: git push, gh create/release/pr, package uploads, mail, mutating HTTP
#   - no destructive commands: rm -rf, git reset --hard, git clean, force operations
#   - no scheduler or persistence (launchctl, crontab, systemctl)
#   - MCP tools that send, post, publish, reply, upload, create or delete are denied
# Denials are written to escalations/ so the author sees what was blocked and why.
set -uo pipefail
VAULT="${AGENT_VAULT:?AGENT_VAULT must be set}"
EXTRA_ROOTS="${FLEET_EXTRA_WRITE_ROOTS:-}"
INPUT="$(cat)"

if ! command -v jq >/dev/null 2>&1; then
  printf '{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"deny","permissionDecisionReason":"jq not installed; boundary cannot read the tool call, failing closed"}}\n'
  exit 0
fi

decide() { # decide allow|deny reason
  if [ "$1" = deny ]; then
    mkdir -p "$VAULT/escalations" 2>/dev/null || true
    printf -- '- %s denied: %s\n' "$(date '+%Y-%m-%d %H:%M')" "$2" >> "$VAULT/escalations/boundary-denials.md" 2>/dev/null || true
  fi
  jq -nc --arg d "$1" --arg r "$2" '{hookSpecificOutput:{hookEventName:"PreToolUse",permissionDecision:$d,permissionDecisionReason:$r}}'
  exit 0
}

in_roots() { # in_roots <abs-path>
  local p="$1" r
  case "$p" in /*) ;; *) p="$PWD/$p";; esac
  # normalise /./ and collapse ../ textually (no symlink resolution: fail toward deny)
  case "$p" in *"/../"*|*"/..") return 1;; esac
  case "$p" in "$VAULT"|"$VAULT"/*) return 0;; esac
  local IFS=:
  for r in $EXTRA_ROOTS; do
    [ -n "$r" ] || continue
    case "$p" in "$r"|"$r"/*) return 0;; esac
  done
  return 1
}

tool="$(printf '%s' "$INPUT" | jq -r '.tool_name // ""')"

case "$tool" in
  Read|Grep|Glob|LS|WebFetch|WebSearch|TodoWrite|Task|Agent)
    decide allow "read-only or internal" ;;
  Write|Edit|MultiEdit|NotebookEdit)
    fp="$(printf '%s' "$INPUT" | jq -r '.tool_input.file_path // .tool_input.notebook_path // ""')"
    [ -n "$fp" ] || decide deny "write with no file path"
    in_roots "$fp" && decide allow "write inside the workspace" || decide deny "write outside the workspace ($fp)" ;;
  Bash)
    cmd="$(printf '%s' "$INPUT" | jq -r '.tool_input.command // ""')"
    lc="$(printf '%s' "$cmd" | tr '[:upper:]' '[:lower:]')"
    if printf '%s' "$lc" | grep -Eq '(^|[;&|[:space:]])git[[:space:]]+push\b|gh[[:space:]]+(repo[[:space:]]+create|release|pr[[:space:]]+(create|merge)|gist[[:space:]]+create)|npm[[:space:]]+publish|twine[[:space:]]+upload|(^|[;&|[:space:]])(sendmail|mail|mutt|osascript)[[:space:]]'; then
      decide deny "outward act (publish/push/send) needs the author: $cmd"
    fi
    if printf '%s' "$lc" | grep -Eq '(curl|wget|http)[^|;&]*(-x[[:space:]]*(post|put|patch|delete)|--data|[[:space:]]-d[[:space:]]|[[:space:]]-f[[:space:]]|--upload|--post)'; then
      decide deny "mutating network request: $cmd"
    fi
    if printf '%s' "$lc" | grep -Eq 'rm[[:space:]]+-[a-z]*r[a-z]*f|rm[[:space:]]+-[a-z]*f[a-z]*r|git[[:space:]]+reset[[:space:]]+--hard|git[[:space:]]+clean[[:space:]]+-[a-z]*f|--force\b|[[:space:]]-f[[:space:]]+origin|(^|[;&|[:space:]])(launchctl|crontab|systemctl)[[:space:]]|(^|[;&|[:space:]])(mkfs|dd)[[:space:]]'; then
      decide deny "destructive or persistence command: $cmd"
    fi
    # shell redirection / tee / cp / mv to an absolute path outside the workspace
    for target in $(printf '%s' "$cmd" | grep -Eo '(>>?|tee( -a)?|cp( -[a-z]+)?( [^ ]+)|mv( -[a-z]+)?( [^ ]+))[[:space:]]*(/|~)[^[:space:];&|]*' | grep -Eo '(/|~)[^[:space:];&|]*$'); do
      t="${target/#\~/$HOME}"
      case "$t" in /dev/null|/dev/stdout|/dev/stderr|/tmp/*|/private/tmp/*|/var/folders/*) continue;; esac
      in_roots "$t" || decide deny "shell write outside the workspace ($t)"
    done
    decide allow "shell command inside the boundary" ;;
  mcp__*)
    if printf '%s' "$tool" | grep -Eiq 'send|post|publish|reply|upload|create|delete|comment|form_input|computer|javascript|execute'; then
      decide deny "MCP tool acts outward ($tool)"
    fi
    decide allow "read-only MCP tool" ;;
  *)
    decide allow "no tripwire for $tool" ;;
esac
