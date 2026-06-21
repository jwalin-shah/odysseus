# cockpit.gsh — Optional gsh REPL wrapper for the Odysseus cockpit.
#
# Source this from ~/.gsh/repl.gsh or run directly:
#   gsh -i -c "source v2/cockpit/cockpit.gsh"
#
# Adds middleware, aliases, and agent definitions that compose ody-*
# commands into a captain-friendly interactive shell.
#
# Requirements (lazy — skip if missing, no hard crash):
#   ody-crew, ody-pane, ody-summarize, ody-policy in PATH or ~/bin/
#   gsh installed via brew or curl

# ── Alias commands (work via gsh's POSIX compatibility) ────────────────────
alias crew='ody-crew'
alias pane='ody-pane'
alias summ='ody-summarize'
alias policy='ody-policy'

# ── utility functions ──────────────────────────────────────────────────────
captain_help() {
  cat <<'END'
Captain, these commands are available:

  crew spawn --kind scout|ship --repo <path> --task "..." [--cmd "..."]
  crew status
  crew watch
  crew peek <id> [lines]
  crew send <id> <text...>
  crew summarize <id>
  crew ship <id>
  crew teardown <id>

  pane list|peek|status|hash|watch|events-drain

  summ [--since 1h|24h|7d] [--run <id>] [--format markdown]
  policy classify <intent>
  policy record <run_id>
  policy check <model> --quota <dim>
END
}

# ── middleware (intercepts gsh input, runs when relevant) ──────────────────
# gsh middleware uses `gsh.use("command.input", fn)`.
# If gsh is not available, these are no-ops.

if command -v gsh >/dev/null 2>&1; then

tool classifyAndRoute(ctx, next) {
  input = ctx.input
  match(input) {
    /^\/crew|^crew /  => true  # pass through, crew handles it
    /^\/pane|^pane /  => true
    /^\/summ|^summ /  => true
    /^\/policy|^policy / => true
    /^\/help|^help|^captain/ => print(captain_help())
                                  return { handled: true }
    /^(fix|investigate|research|look at|audit|check|find|implement|build) / => {
      # Classify via ody-policy and suggest crew spawn
      decision = exec("ody-policy classify " + input)
      print("→ " + decision.stdout.strip())
      print("  Try: crew spawn --kind " + decision.stdout.strip() +
            " --repo <path> --task \"" + input + "\"")
      return { handled: true }
    }
    /./ => {  # passthrough for all other input
      return next(ctx)
    }
  }
}

gsh.use("command.input", classifyAndRoute)


tool scoutAgent {
  model: gsh.models.workhorse,
  systemPrompt: "You are a scout: you investigate, analyze, and report. Never modify files.",
}

tool shipAgent {
  model: gsh.models.best,
  systemPrompt: "You are a ship agent: you implement fixes, write tests, and ship through no-mistakes.",
}

tool summarizer {
  model: gsh.models.cheap,
  systemPrompt: "Compress tool traces and events into hypernym summaries.",
}

end

# ── fallback: help when not in gsh ────────────────────────────────────────
if [ -z "${GSH_SHELL:-}" ]; then
  echo "cockpit.gsh: sourced from a plain shell — ody-* commands are available by alias."
  echo "  For the full REPL experience, run: gsh -i"
  echo "  Or: source cockpit.gsh inside gsh"
fi
