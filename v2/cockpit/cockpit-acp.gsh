# cockpit-acp.gsh — Agent Client Protocol (ACP) support for Odysseus cockpit.
#
# Source this from cockpit.gsh or load on demand:
#   source v2/cockpit/cockpit-acp.gsh
#
# Adds ACP agent definitions and @-mention middleware for delegating to
# Claude Code, Codex, OpenCode, and Pioneer via ody-crew scout workers.
#
# ACP packages available (npm):
#   @agentclientprotocol/claude-agent-acp  — Claude Code via ACP
#   @agentclientprotocol/codex-acp         — Codex via ACP
#   @agentclientprotocol/opencode-acp      — OpenCode via ACP (not yet published)
#
# For now, all agents use plain subprocess dispatch through ody-crew for
# visibility (crewmate output is visible to the captain). ACP stateful
# sessions can be wired later when the protocol matures.
#
# Requirements (lazy — skip if missing, no hard crash):
#   ody-crew in PATH or ~/bin/
#   gsh REPL (for middleware; agent definitions work standalone)
#
# ── ACP agent definitions ──────────────────────────────────────────────────
# Each agent is a named capability that can be dispatched via ody-crew.
# The `acp` field records the npm package for future ACP protocol wiring.

declare -A ACP_AGENTS

ACP_AGENTS[ClaudeCode]='{
  "name": "ClaudeCode",
  "binary": "claude",
  "acp_package": "@agentclientprotocol/claude-agent-acp",
  "acp_binary": "claude-agent-acp",
  "description": "Anthropic Claude Code — full agent with file read/write, shell, search",
  "spawn_kind": "scout",
  "default_cmd": "claude --dangerously-skip-permissions -p"
}'

ACP_AGENTS[Codex]='{
  "name": "Codex",
  "binary": "codex",
  "acp_package": "@agentclientprotocol/codex-acp",
  "acp_binary": "codex-acp",
  "description": "OpenAI Codex CLI — code generation and editing agent",
  "spawn_kind": "scout",
  "default_cmd": "codex exec"
}'

ACP_AGENTS[OpenCode]='{
  "name": "OpenCode",
  "binary": "opencode",
  "acp_package": null,
  "acp_binary": null,
  "description": "OpenCode — open-source coding agent (no ACP package yet)",
  "spawn_kind": "scout",
  "default_cmd": "opencode"
}'

ACP_AGENTS[Pioneer]='{
  "name": "Pioneer",
  "binary": "claude",
  "acp_package": "@agentclientprotocol/claude-agent-acp",
  "acp_binary": "claude-agent-acp",
  "description": "Claude Code via Pioneer account (claude-rollover route p)",
  "spawn_kind": "scout",
  "default_cmd": "claude-rollover run pioneer --dangerously-skip-permissions -p"
}'

# ── utility functions ───────────────────────────────────────────────────────

acp_help() {
  cat <<'END'
ACP Agent Delegation — available @-mentions:

  @claude <query>    → delegate to Claude Code via ody-crew scout
  @codex <query>     → delegate to Codex via ody-crew scout
  @opencode <query>  → delegate to OpenCode via ody-crew scout
  @pioneer <query>   → delegate to Pioneer (Claude, Pioneer account) via ody-crew scout

  acp-list           → show registered ACP agents and their status
  acp-install <name> → install ACP npm package for an agent (if available)
END
}

acp_list() {
  local name json binary acp_pkg acp_bin status
  echo "Registered ACP agents:"
  echo "────────────────────────────────────────────────────────────"
  for name in "${!ACP_AGENTS[@]}"; do
    json="${ACP_AGENTS[$name]}"
    binary=$(echo "$json" | python3 -c "import sys,json; print(json.load(sys.stdin)['binary'])")
    acp_pkg=$(echo "$json" | python3 -c "import sys,json; p=json.load(sys.stdin).get('acp_package'); print(p or 'none')")
    acp_bin=$(echo "$json" | python3 -c "import sys,json; b=json.load(sys.stdin).get('acp_binary'); print(b or 'none')")

    if command -v "$binary" >/dev/null 2>&1; then
      status="binary: OK"
    else
      status="binary: MISSING"
    fi

    if [[ "$acp_bin" != "none" ]] && command -v "$acp_bin" >/dev/null 2>&1; then
      status="$status | ACP: OK"
    elif [[ "$acp_bin" != "none" ]]; then
      status="$status | ACP: not installed (npm install $acp_pkg)"
    else
      status="$status | ACP: N/A"
    fi

    printf "  %-12s  %s\n" "$name" "$status"
  done
}

acp_install() {
  local name="$1"
  local json="${ACP_AGENTS[$name]}"
  if [[ -z "$json" ]]; then
    echo "Unknown agent: $name. Try: ClaudeCode, Codex, OpenCode, Pioneer"
    return 1
  fi
  local acp_pkg
  acp_pkg=$(echo "$json" | python3 -c "import sys,json; p=json.load(sys.stdin).get('acp_package'); print(p or '')")
  if [[ -z "$acp_pkg" || "$acp_pkg" == "null" ]]; then
    echo "No ACP package available for $name"
    return 1
  fi
  echo "Installing $acp_pkg..."
  npm install -g "$acp_pkg"
}

# ── dispatch: delegate a query to an agent via ody-crew scout ───────────────

acp_dispatch() {
  local agent_name="$1"
  shift
  local query="$*"
  local json="${ACP_AGENTS[$agent_name]}"

  if [[ -z "$json" ]]; then
    echo "Unknown ACP agent: $agent_name"
    echo "Available: ${!ACP_AGENTS[*]}"
    return 1
  fi

  local binary spawn_kind default_cmd
  binary=$(echo "$json" | python3 -c "import sys,json; print(json.load(sys.stdin)['binary'])")
  spawn_kind=$(echo "$json" | python3 -c "import sys,json; print(json.load(sys.stdin)['spawn_kind'])")
  default_cmd=$(echo "$json" | python3 -c "import sys,json; print(json.load(sys.stdin)['default_cmd'])")

  if ! command -v "$binary" >/dev/null 2>&1; then
    echo "ACP: $agent_name binary '$binary' not found — cannot dispatch"
    return 1
  fi

  if ! command -v ody-crew >/dev/null 2>&1; then
    echo "ACP: ody-crew not found — cannot dispatch worker"
    return 1
  fi

  local repo
  repo="$(pwd)"

  echo "ACP: dispatching to $agent_name (scout) via ody-crew..."
  echo "  Task: $query"
  echo "  Repo: $repo"
  echo ""

  # Spawn a scout worker via ody-crew.
  # The --cmd flag overrides the default worker command so the pane runs
  # the agent binary directly with the query.
  ody-crew spawn \
    --kind "$spawn_kind" \
    --repo "$repo" \
    --task "$query" \
    --cmd "$default_cmd \"$query\""

  local exit_code=$?
  if [[ $exit_code -eq 0 ]]; then
    echo ""
    echo "ACP: $agent_name scout dispatched. Use 'crew watch' or 'crew status' to monitor."
  else
    echo "ACP: dispatch failed (exit $exit_code)"
  fi
  return $exit_code
}

# ── middleware (gsh REPL integration) ───────────────────────────────────────
# These @-mention handlers are registered as gsh middleware when available.
# If gsh is not loaded, they work as standalone shell functions.

acp_handle_mention() {
  local input="$1"
  local agent="" query=""

  case "$input" in
    @claude\ *)
      agent="ClaudeCode"
      query="${input#@claude }"
      ;;
    @codex\ *)
      agent="Codex"
      query="${input#@codex }"
      ;;
    @opencode\ *)
      agent="OpenCode"
      query="${input#@opencode }"
      ;;
    @pioneer\ *)
      agent="Pioneer"
      query="${input#@pioneer }"
      ;;
    acp-list)
      acp_list
      return 0
      ;;
    acp-help)
      acp_help
      return 0
      ;;
    acp-install\ *)
      acp_install "${input#acp-install }"
      return $?
      ;;
    *)
      return 1  # not an ACP mention
      ;;
  esac

  acp_dispatch "$agent" "$query"
  return $?
}

# ── gsh middleware registration ─────────────────────────────────────────────
# Only registers if gsh is available and the middleware API exists.

if command -v gsh >/dev/null 2>&1; then

tool acpMentionRouter(ctx, next) {
  input = ctx.input
  match(input) {
    /^@claude /  => return { handled: true, output: acp_dispatch("ClaudeCode", input.replace(/^@claude /, "")) }
    /^@codex /   => return { handled: true, output: acp_dispatch("Codex", input.replace(/^@codex /, "")) }
    /^@opencode /=>
      return { handled: true, output: acp_dispatch("OpenCode", input.replace(/^@opencode /, "")) }
    /^@pioneer / => return { handled: true, output: acp_dispatch("Pioneer", input.replace(/^@pioneer /, "")) }
    /^acp-/      => return { handled: true, output: acp_handle_mention(input) }
    /./          => return next(ctx)
  }
}

gsh.use("command.input", acpMentionRouter)

end

# ── standalone shell integration ────────────────────────────────────────────
# When sourced from a plain shell (not gsh), dispatch is manual via
# acp_dispatch or the acp_handle_mention function.
#
# Usage in standalone shell mode:
#   source v2/cockpit/cockpit-acp.gsh
#   acp_dispatch ClaudeCode "your query here"
#   acp_dispatch Codex "your query here"
#   # or use acp_handle_mention with the full @mention string:
#   acp_handle_mention "@claude your query here"

if [[ -z "${GSH_SHELL:-}" ]]; then
  echo "cockpit-acp.gsh: loaded ACP agent definitions (standalone shell mode)."
  echo "  Use: acp_dispatch ClaudeCode|Codex|OpenCode|Pioneer \"query\""
  echo "  Or:  acp-list, acp-help"
  echo "  For the full REPL experience with @-mention middleware, run: gsh -i"
fi