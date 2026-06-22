# cockpit.gsh — gsh REPL wrapper for the Odysseus cockpit (VERIFIED on gsh 1.11.0).
# Load from ~/.gsh/repl.gsh with:  source("/Users/jwalinshah/projects/odysseus/v2/cockpit/cockpit.gsh")

# ── captain help text ──────────────────────────────────────────────────────
tool captain_help() {
  print("Captain, these commands are available:")
  print("  crew spawn|status|watch|peek|send|summarize|ship|teardown")
  print("  pane list|peek|status|hash|watch|events-drain")
  print("  summ [--since 1h|24h|7d] [--run <id>]")
  print("  policy classify <intent>")
}

# ── middleware: route captain intent → ody-* subprocesses ──────────────────
tool cockpitRouter(ctx, next) {
  input = ctx.input.trim()
  if (input == "") { return next(ctx) }

  # explicit help
  if (input == "help" || input == "captain") {
    captain_help()
    return { handled: true }
  }

  # natural-language intent verbs → classify via ody-policy, suggest a spawn
  verbs = ["fix ", "investigate ", "research ", "look at ", "audit ", "check ", "find ", "implement ", "build "]
  for (v of verbs) {
    if (input.startsWith(v)) {
      decision = exec(`ody-policy classify ${input}`)
      kind = decision.stdout.trim()
      print(`→ ody-policy says: ${kind}`)
      print(`  Try: crew spawn --kind ${kind} --task "${input}"`)
      return { handled: true }
    }
  }

  # everything else: fall through to the shell (crew/pane/summ run as commands)
  return next(ctx)
}

gsh.use("command.input", cockpitRouter)
print("cockpit.gsh loaded — type 'help' for captain commands")
