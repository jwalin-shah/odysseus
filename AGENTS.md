# Odysseus — Agent Guide

Project-intrinsic knowledge for crewmate agents working in this repo. Sourced from
`README.md`, `CONTRIBUTING.md`, `docs/setup.md`, `specs/architecture-runtime-inventory.md`,
`Dockerfile`, and `.github/workflows/`. Sections are tagged for quick lookup.

<!-- AGENTS:BUILD_AND_TEST -->
## Build & Test

**Branch model.** `dev` is the default branch and where all PRs land. `main` is the
curated/stable branch, fast-forwarded to a tested `dev` commit at each release. **Open
every PR against `dev`, not `main`** — the GitHub base dropdown defaults to `dev`.

**Docker (recommended for testing):**

```bash
cp .env.example .env
docker compose up -d --build
docker compose logs --tail=120 odysseus    # first admin password is printed here
```

App serves at `http://localhost:7000` once containers are healthy.

**Native development (Python 3.11+):**

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python -m uvicorn app:app --host 127.0.0.1 --port 7000
```

**Checks — run the smallest relevant set for your change:**

```bash
python -m pytest                                          # tests
python -m py_compile app.py routes/*.py src/*.py          # syntax
node --check static/js/<file-you-changed>.js              # JS syntax
docker compose config                                     # for compose changes
```

**CI (`.github/workflows/ci.yml`)** runs three jobs:
- `python-syntax` — `python -m compileall -q app.py core routes src services scripts tests` (must pass).
- `node-syntax` — `node --check` over `static/app.js` and `static/js/**/*.js` (skips vendored `static/lib`).
- `python-tests` — `python -m pytest -q`. Currently `continue-on-error: true` (known
  flaky/env-dependent failures), and skipped entirely for docs-only PRs (paths matching
  `docs/`, `*.md`, `.github/*.md`).

**Commits:** Conventional Commits — `type(scope): summary` (`fix`, `feat`, `refactor`,
`docs`, `test`, `chore`, `ci`). Keep PRs small and single-purpose.

**Code conventions:** never hardcode writable paths or loopback URLs. Use named constants
from `src/constants.py` (e.g. `AUTH_FILE`, `SETTINGS_FILE`, `CHROMA_DIR`, `DATA_DIR`) and
`internal_api_base()` from `src.constants` instead of `http://localhost:7000`. Add a
constant rather than repeating a literal. `core/constants.py` only re-exports `src/constants.py`.

<!-- AGENTS:ARCHITECTURE -->
## Architecture

FastAPI app booting from `app.py` (the entrypoint; there is no `main.py`). High-level layout:

```
app.py        # FastAPI entry point
core/         # auth, database, middleware, constants, session_manager (10 files)
src/          # llm_core, agent_loop, agent_tools/, chat_processor, search/ (95 flat .py files + 2 subdirs)
routes/       # chat, session, document, memory, model … HTTP handlers (54 flat .py files)
services/     # docs, memory, search, hwfit (Cookbook)
static/       # index.html + app.js + style.css + js/ (modular front-end)
docs/         # landing page (index.html) + preview clips
mcp_servers/  # MCP server implementations (5 files)
tests/        # ~583 test files
```

**High-risk / oversized modules** (see `specs/architecture-runtime-inventory.md`):
- `core/database.py` — **102 importers**, the most depended-upon module. Any split is
  the highest-risk refactor; tackle it **last**, never first.
- `src/tool_implementations.py` — ~4,000 lines, 33 `do_*` tool functions, 17 importers.
- `src/agent_loop.py` — ~3,000 lines, 22 importers.
- `static/style.css` (~36k lines) and `static/js/document.js` (~9.7k lines) are tracked
  for modularization separately (#2617).

**Layer rule:** `routes/ → src/ → core/` is the intended direction. A handful of inline
(function-body) imports from `src/` back into `routes/` exist — treat them as a smell, not
a pattern to copy. Don't add top-level `src → routes` imports.

**Data:** all user data lives in `data/` (gitignored): `app.db` (sessions, messages,
documents), `memory.json`, `presets.json`, `uploads/`, `personal_docs/`, `chroma/`,
`settings.json`. Vector memory uses ChromaDB; embeddings via an OpenAI-compatible endpoint.

<!-- AGENTS:DEPLOYMENT -->
## Deployment

**Docker image:** `python:3.14-slim` base (see `Dockerfile`). System deps: `tmux`
(Cookbook background downloads/serves), `openssh-client` (remote server probes),
`git`/`cmake` (llama.cpp builds), `nodejs`/`npm` (browser MCP), `gosu` (privilege drop).
Optional AGPL extras (PyMuPDF, etc.) are opt-in via `--build-arg INSTALL_OPTIONAL=true`.
Container `EXPOSE`s 7000 and runs `uvicorn app:app --host 0.0.0.0 --port 7000` through
`docker/entrypoint.sh`, which drops to `PUID/PGID` (default 1000:1000) and repairs
ownership on bind-mounted `/app/data` and `/app/logs`.

**Compose stack:** `docker-compose.yml` starts Odysseus + ChromaDB + SearXNG + ntfy, all
bound to `127.0.0.1` by default. GPU overlays: `docker/gpu.nvidia.yml` /
`docker/gpu.amd.yml` (CLI via `COMPOSE_FILE`), or standalone
`docker-compose.gpu-nvidia.yml` / `docker-compose.gpu-amd.yml` for single-file stack UIs.

**Key `.env` settings** (deployment-level defaults; most config is in-app under Settings):

| Variable | Default | Purpose |
|---|---|---|
| `APP_BIND` | `127.0.0.1` | Host bind address; `0.0.0.0` only for intentional LAN/proxy access |
| `APP_PORT` | `7000` | Host web UI port |
| `AUTH_ENABLED` | `true` | Login; keep `true` for any network-accessible deploy |
| `LOCALHOST_BYPASS` | `false` | Dev-only loopback auth bypass; keep `false` when shared |
| `SECURE_COOKIES` | `false` | `true` when served via HTTPS behind a trusted proxy |
| `DATABASE_URL` | `sqlite:///./data/app.db` | DB connection string |
| `CHROMADB_HOST`/`PORT` | `localhost`/`8100` | Docker overrides to `chromadb`/`8000` |

**Security posture:** treat Odysseus as an admin console (shell, file, model-serving
tools). Serve plain HTTP only behind a trusted reverse proxy / private access gateway;
keep raw service ports (SearXNG 8080, ntfy 8091, ChromaDB 8100, Ollama 11434, model APIs
8000–8020) internal-only. Before publishing a fork, run `git status --short` and confirm
no `.env`, `data/`, `logs/`, uploads, or local DBs are staged.

<!-- AGENTS:KNOWN_QUIRKS -->
## Known Quirks

- **`pytest` is informational in CI.** The `python-tests` job is `continue-on-error: true`
  due to known test-isolation and embedding-model-assertion flakiness. A red pytest does
  **not** block merge today, but don't use that as cover for regressions — the syntax jobs
  (`compileall`, `node --check`) are the hard gates.
- **macOS native port is 7860, not 7000.** `start-macos.sh` runs uvicorn on `7860` because
  AirPlay commonly holds `7000`. Use `./start-macos.sh` (reads `.env`) on Apple Silicon.
- **Apple Silicon GPU needs native, not Docker.** Docker on macOS can't reach Metal, so
  Cookbook serves on CPU only inside containers. Run natively for GPU-accelerated serving.
- **MLX-only models are not served by Odysseus.** vLLM/SGLang are CUDA/ROCm-only (no
  macOS). On macOS, Cookbook uses llama.cpp/Ollama for Metal.
- **`chromadb-client` breaks embedded ChromaDB.** If the HTTP-only `chromadb-client`
  package is installed alongside full `chromadb`, ChromaDB silently falls back to HTTP-only
  and fails. Fix: `pip uninstall chromadb-client -y && pip install --force-reinstall chromadb`.
- **GPU passthrough ≠ working CUDA build.** `nvidia-smi` passing inside the container only
  confirms Docker device access; llama.cpp still needs `cudart`/CUDA Toolkit. `Unable to
  find cudart library` is a Cookbook/llama.cpp build issue — reinstall the serve engine via
  **Cookbook → Dependencies**, it is not a Docker passthrough failure.
- **`requirements.txt` is intentionally unpinned.** Two installs at different times can
  resolve different versions. Use `uv pip compile`/`uv pip sync` for a reproducible
  `requirements.lock` (gitignored, platform-specific).
- **Outlook/Office 365 email fails with passwords.** Accounts use IMAP/SMTP
  username-password auth; Microsoft mailboxes generally require OAuth. See
  `docs/email-outlook.md`.
- **Browser MCP only registers if `@playwright/mcp` is already in the npx cache.** A fresh
  install skips it (logged) rather than blocking on a ~300MB download. Run
  `npx -y @playwright/mcp@latest --version` once, then restart, to enable it.
