# Jwalin Shah - Master Profile
**Contact:** Fremont, CA · (408) 908-9659 · jwalinshah13@gmail.com
**Links:** [github.com/jwalin-shah](https://github.com/jwalin-shah) · [linkedin.com/in/jwalin-shah](https://linkedin.com/in/jwalin-shah)
**Title:** AI Systems Engineer · Evaluation & Reliability · Tool-Augmented Reasoning · Applied AI
**Objective:** Builds systems to measure, diagnose, and improve LLM behavior under real-world constraints.

## SELECTED IMPACT
*   **Evaluation at Scale** — Built telemetry across 3,600+ tasks to diagnose grounded reasoning failures. Ranked top tier on a 246-task financial benchmark (180+), outperforming baseline agents.
*   **LLM Reliability** — Demonstrated that constraining LLMs to deterministic computation pipelines reduces hallucination rates to <5% on real-world financial tasks.
*   **Real-World Systems** — Scaled robotics data operations to 30+ operators across five platforms, improving task success by ~40% and reducing overhead by ~50%.

## TECHNICAL SKILLS
*   **AI Systems:** Tool-augmented LLMs, retrieval pipelines (BM25 + embeddings), structured extraction, deterministic computation, on-device inference
*   **Eval & Reliability:** Benchmark harnesses, telemetry, failure mode analysis (tool thrashing, retrieval errors, temporal misalignment), hallucination measurement, RL environments
*   **Tools:** Python, SQL, Bash, FastAPI, SQLite + sqlite-vec, MLX, DSPy, TensorFlow, MediaPipe

## PROFESSIONAL EXPERIENCE
**Sentient Arena (Cohort 0) | Research Contributor – Grounded Reasoning (March 2026)**
*   Built a multi-agent LLM system for grounded financial reasoning, ranking top tier (180+) on a 246-task benchmark by replacing in-model arithmetic with structured retrieval and deterministic computation.
*   Developed evaluation infrastructure across 15+ runs (3,600+ tasks), analyzing stochastic behavior, tool use patterns, and system-level performance.
*   Identified that retrieval errors and tool selection — not model reasoning — drive the majority of failures in grounded LLM tasks, validated across 3,600+ evaluations.
*   Improved accuracy via system-level fixes: tool prioritization, forced-answer heuristics, and database architecture changes.

**Skild AI | Data Operations Lead (ML Systems & Reliability) (San Mateo, CA · Jul–Nov 2025)**
*   Built and scaled data validation and collection systems across five robotic platforms supporting model training and evaluation.
*   Developed Python automation pipelines reducing operational overhead by ~50% and improving downstream task success by ~40%.
*   Primary technical operator for 25+ live robot demos during $1B Series C; maintained zero-failure execution under pressure.
*   Debugged edge-case failures in perception, manipulation, and locomotion systems in real-world deployment environments.

## FEATURED PROJECTS
**Jarvis — Local-First AI Assistant (GitHub · 736 commits)**
*   Privacy-first assistant on Apple Silicon (8GB M2 Air): MLX inference + SQLite/sqlite-vec retrieval, zero cloud dependencies.
*   Dual-path architecture: fast-path (<0.42s, ~230 tok/s) for simple queries; background pipeline for complex grounded reasoning.
*   Evaluation harness across 37 model configs optimizing latency, retrieval quality (Hit@5), and hallucination rates (<5%).

**Squat Coach (InstaLILY AI Hackathon)**
*   Real-time exercise analysis using MediaPipe pose estimation with temporal smoothing for joint angle tracking on consumer hardware.

**OpenEnv — RL Environment Design (OpenEnv Hackathon 2026)**
*   Custom RL environment with FastAPI state transitions and multi-dimensional reward; GRPO training with ~80% success baseline.

## RESEARCH & ANALYSIS
*   Systematic failure analysis across 3,600+ LLM benchmark evaluations quantifying error attribution across system components.
*   Found that retrieval errors and tool selection — not reasoning capability — account for the dominant share of failures in grounded tasks.
*   Demonstrated that deterministic computation + structured extraction reduces hallucination rates from baseline to <5%.

## EDUCATION & LEADERSHIP
**University of Texas at Dallas — B.S. Computer Science (GPA: 3.67)**
*   **UTD Ultimate Frisbee — Captain:** Led 30-member competitive program through recruitment, budgeting ($20K+), and tournament logistics.
*   **UTD Chess Club:** USCF 1832 (91st percentile). Trained with GMs/FMs; coached 50+ students in positional analysis.
