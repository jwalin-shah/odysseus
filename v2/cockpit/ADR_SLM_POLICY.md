# ADR: SLM Policy Router for Odysseus Cockpit

**Status**: Accepted (2026-06-21)
**Scope**: Cockpit policy routing layer within `odysseus/v2/cockpit/`
**PR**: None yet — blueprint document

---

## Decision

Replace (or augment) `ody-policy`'s heuristic bash-grep classifier with a small local model (SLM) trained on cockpit decision traces. The SLM acts as a first-pass router before `ody-crew` dispatch, classifying user intent into one of four actions: `scout`, `ship`, `direct`, `blocked`.

---

## Why a small local model?

1. **Free inference.** MiniMax-M3 via tokenrouter costs $0 per call — tokenrouter rotates free-tier keys automatically. A heuristic grep also costs $0; a local classifier adds decision quality without marginal cost.

2. **No latency.** No API round-trip, no queue, no rate limits. The classifier runs locally, sub-10ms per classification, fitting naturally into the cockpit hot path before crew spawning.

3. **Privacy.** Intents stay on device. No intent text ever leaves the Mac.

4. **Improves with data.** The heuristic is frozen; a trained classifier gets better as trace volume grows. Each `ody-policy record` invocation adds a training example.

5. **Self-correcting.** The `--interactive` training loop lets operators correct misclassifications, building a labeled corpus that compounds over time.

---

## Architecture

```
                   ┌─ User Intent ───────────────────┐
                   │ "Investigate the tokenrouter     │
                   │  key rotation bug in v2/src/"    │
                   └──────────────┬───────────────────┘
                                  │
                                  ▼
                   ┌─ SLM Policy Router ─────────────┐
                   │  Lightweight intent classifier    │
                   │  (TF-IDF + logistic regression    │
                   │   or MiniMax-M3 via tokenrouter)  │
                   ├──────────────────────────────────┤
                   │  Output: scout|ship|direct|blocked│
                   └──────┬───────┬───────┬───────────┘
                          │       │       │
                    scout  │  ship │ direct│ blocked
                          ▼       ▼       ▼
                   ody-crew  ody-crew   (answer  (prompt
                   scout     ship       directly) human)
```

### Components

| Component | Description |
|---|---|
| **Trace collector** | `ody-policy record` writes (intent, decision, context) to `traces.jsonl` |
| **Training pipeline** | `ody-policy-train.py` converts traces → feature vectors → training examples |
| **Feature extractor** | Tokenization, keyword presence flags, question detection |
| **Classifier** | Lightweight model (TF-IDF + logistic regression initial, MiniMax-M3 as SLM target) |
| **Router** | Checks classifier output, calls `ody-crew` with appropriate mode |

### Integration

```
ody-crew spawn --kind scout ...   → records trace via ody-policy record
ody-policy classify <intent>       → heuristic fallback until SLM is trained
ody-policy-train.py                 → offline training after 500+ traces
ody-policy serve                    → future: load SLM, classify in hot path
```

---

## Training pipeline

```
traces.jsonl
    │
    ▼
ody-policy-train.py
    │
    ├── analyze: word frequency, confusion detection, feature extraction
    │
    ├── emit training-examples.jsonl (structured feature vectors)
    │
    └── --interactive: human review loop → training-examples-corrected.jsonl
                                      │
                                      ▼
                                Lightweight classifier
                                (scikit-learn / ONNX / tokenrouter)
```

### Feature vector (per example)

```json
{
  "intent": "original text",
  "decision": "scout|ship|direct|blocked",
  "features": {
    "tokens": ["investigate", "the", "tokenrouter", "..."],
    "token_count": 8,
    "has_code_keyword": false,
    "has_question_keyword": false,
    "has_research_keyword": true,
    "has_blocked_keyword": false,
    "first_word": "investigate",
    "ends_with_question": false
  }
}
```

### Training steps

1. **Phase 0 — Heuristic baseline** (current). `ody-policy classify` uses bash grep.
2. **Phase 1 — Feature collection** (now). Record every cockpit spawn with (intent, decision, outcome).
3. **Phase 2 — Training data** (500+ traces). `ody-policy-train.py --interactive` to build corrected corpus.
4. **Phase 3 — Lightweight model** (500-2000 traces). Train TF-IDF + logistic regression as first classifier.
5. **Phase 4 — SLM distillation** (2000+ traces). Fine-tune MiniMax-M3 on the labeled corpus.
6. **Phase 5 — First-pass router**. SLM runs inline before `ody-crew` dispatch, with heuristic fallback.

---

## Evaluation

Compare three decision methods:

| Method | Description | Baseline |
|---|---|---|
| **Heuristic** | Current bash-grep rules | Always-on |
| **SLM** | Trained local classifier | When 500+ traces |
| **Ideal** | Post-hoc human judgment | For evaluation only |

Metrics:
- **Accuracy**: fraction matching ideal decision
- **Precision/Recall** per class (scout, ship, direct, blocked)
- **Latency**: p50/p99 classification time
- **Confusion matrix**: which pairs are hardest to separate

---

## Data collection plan

Every cockpit spawn should record:

```
ody-crew spawn --kind scout --task "..."
  → internally calls ody-policy record <run_id>
  → writes to ~/.odysseus/cockpit/policy/traces.jsonl:
     {
       "ts": "2026-06-21T16:48:57Z",
       "run_id": "scout-treehouse-smoke",
       "model": "claude-a",
       "kind": "scout",
       "intent": "Investigate treehouse TLS cert rotation",
       "decision": "scout",
       "statuses": "spawn|worktree|running"
     }
```

**Target: 500+ traces before first SLM training attempt.**

At 500 traces across all 4 classes, we expect ~50-100 per class minimum for viable training. At 2000+, the SLM should significantly outperform the heuristic.

---

## What NOT to do

1. **Don't use large models (GPT, Claude, Fable) for routing.** The whole point is to avoid LLM latency/cost for a simple 4-way classification.
2. **Don't build the classifier before the data.** Heuristic is fine for now. Data collection is the bottleneck.
3. **Don't over-engineer features.** Token presence flags + TF-IDF is sufficient for 4-class intent classification.
4. **Don't ship without a fallback.** Heuristic must always be available if the SLM returns low confidence.

---

## Open questions

1. Should the SLM be a standalone process or a Python import inside `ody-policy`?
2. Retraining cadence: after every N new traces, or on demand?
3. Confidence threshold: below what score should we fall back to heuristic?
4. Should `ody-policy record` capture the outcome (success/failure) for richer training labels?
