# REMOTE_PROPOSED.md — odysseus

**Status:** existing origin does NOT match the workpack's expected `jwalin-shah/odysseus.git`.
**Worker action taken:** none (per HARD RED LINE: no `git remote add` without review).
**Date:** 2026-06-12

## Current state

```
$ git remote -v
origin  https://github.com/pewdiepie-archdaemon/odysseus (fetch)
origin  https://github.com/pewdiepie-archdaemon/odysseus (push)
```

The existing `origin` is owned by **`pewdiepie-archdaemon`**, not by `jwalin-shah`. The workpack
proposed `git@github.com:jwalin-shah/odysseus.git`. You should decide:

- **Option A — repoint origin to your GitHub:** create the empty private repo
  `jwalin-shah/odysseus` on GitHub, then:
  ```bash
  cd ~/projects/odysseus
  git remote set-url origin git@github.com:jwalin-shah/odysseus.git
  git remote -v   # confirm
  ```
- **Option B — add your repo as a second remote (e.g. `gh`)** and keep the original:
  ```bash
  cd ~/projects/odysseus
  git remote add jwalin git@github.com:jwalin-shah/odysseus.git
  git remote -v
  ```
- **Option C — keep `pewdiepie-archdaemon/odysseus` as-is.** Document why in this file.

## Local branches and unpushed state

| Branch | Tracking | Status | Last commit |
|---|---|---|---|
| `dev` | `origin/dev` | in sync | `43a101d` refactor(tests): finish shared CLI loader adoption |
| `hygiene/20260608` | none | 9 commits ahead, never pushed | `012be87` V1 orchestrator: bg-implementer + defensive-architect + miner config |
| `v3/go-router-port` | none | 9 commits ahead, never pushed (same HEAD as `hygiene/20260608`) | `012be87` |

## Verification commands (run BEFORE any push)

```bash
cd ~/projects/odysseus
git remote -v                                       # confirm new URL is in place
git status                                          # working tree clean
git log --oneline origin/dev..dev                   # dev should be empty (in sync)
git log --oneline origin/main..main 2>/dev/null     # if origin/main exists
git log --oneline -5 dev                            # eyeball latest
```

## Push commands (run AFTER verification, only if you decide to push)

```bash
cd ~/projects/odysseus
# Push tracked branch first
git push origin dev                                 # only if origin is your repo

# Push local-only branches (these have NO upstream yet)
git push -u origin hygiene/20260608
git push -u origin v3/go-router-port
```

## What is NOT being done by the worker

- No `git remote add origin` was run.
- No `git push` was run.
- No tracked file was modified.
- No branch was deleted or rebased.

## Kill criteria reminder

If you choose Option A, the existing remote URL is destroyed on `git remote set-url`.
Make sure `pewdiepie-archdaemon/odysseus` is not the canonical home of this repo
before running it.
