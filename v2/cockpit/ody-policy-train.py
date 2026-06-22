#!/usr/bin/env python3
"""
ody-policy-train: Convert cockpit policy traces into SLM training examples.

Reads ~/.odysseus/cockpit/policy/traces.jsonl, analyzes decision patterns,
and produces labeled training examples for a compact intent classifier.

Output:
  - summary of current traces (counts per decision class)
  - structured examples in JSONL format ready for fine-tuning
  - feature analysis: which intent words correlate with which decisions

Usage:
  python3 ody-policy-train.py [--limit N] [--interactive] [--state-dir PATH]
"""

import argparse
import json
import os
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path


# ── constants ─────────────────────────────────────────────────────────────────

DECISION_CLASSES = {"scout", "ship", "direct", "blocked"}
CODE_KEYWORDS = {"fix", "implement", "add", "change", "update", "refactor",
                 "rewrite", "migrate", "build", "create", "ship", "deploy",
                 "patch", "merge", "push", "pr", "commit", "branch", "test",
                 "debug", "code"}
QUESTION_KEYWORDS = {"what", "who", "when", "where", "why", "how", "which",
                     "is", "are", "was", "were", "do", "does", "did", "can",
                     "could", "would", "should", "has", "have", "does"}
RESEARCH_KEYWORDS = {"investigate", "research", "find", "search", "examine",
                     "audit", "analyze", "check", "list", "show", "describe",
                     "report", "inspect", "explore", "survey", "map", "scout",
                     "read", "look", "understand"}
BLOCKED_KEYWORDS = {"can't", "cannot", "unable", "blocked", "stuck", "help",
                    "confused", "error", "fail", "broken", "not working",
                    "how do", "how to", "what is wrong", "problem"}


# ── utilities ─────────────────────────────────────────────────────────────────

def tokenize(text: str) -> list[str]:
    """Split text into lowercase tokens."""
    return re.findall(r"[a-zA-Z']+(?:'[a-zA-Z]+)?", text.lower())


def extract_features(intent: str) -> dict:
    """Extract feature vector from intent text."""
    tokens = tokenize(intent)
    token_set = set(tokens)
    return {
        "tokens": tokens,
        "token_count": len(tokens),
        "has_code_keyword": bool(token_set & CODE_KEYWORDS),
        "has_question_keyword": bool(token_set & QUESTION_KEYWORDS),
        "has_research_keyword": bool(token_set & RESEARCH_KEYWORDS),
        "has_blocked_keyword": bool(token_set & BLOCKED_KEYWORDS),
        "first_word": tokens[0] if tokens else "",
        "ends_with_question": intent.strip().endswith("?"),
    }


def heuristic_decision(intent: str) -> str:
    """Replicate ody-policy's heuristic classifier for comparison."""
    lowered = intent.lower().strip()

    # Direct answer patterns
    if re.search(
        r"^(what|who|when|where|why|how many|how much|is there|does .* exist)\b", lowered
    ):
        if re.search(
            r"^(what|who|when|where|why)\s+(is|are|was|were|do|does|did)\b", lowered
        ):
            return "direct"

    # Scout patterns
    if re.search(
        r"\b(investigate|research|find|search|look at|examine|audit|analyze|"
        r"check|list|show|describe|report|inspect|explore|survey|map|diagram|scout)\b",
        lowered,
    ):
        return "scout"

    # Ship patterns
    if re.search(
        r"\b(fix|implement|add|change|update|refactor|rewrite|migrate|build|"
        r"create|ship|deploy|patch|merge|push|pr)\b",
        lowered,
    ):
        return "ship"

    # Blocked patterns
    if re.search(r"\b(can't|unable|blocked|stuck|help|how do)\b", lowered):
        return "blocked"

    return "scout"


# ── analysis functions ────────────────────────────────────────────────────────

def word_frequency(traces: list[dict]) -> dict[str, list[tuple[str, int]]]:
    """Compute top-10 keywords per decision class (word frequency analysis)."""
    class_words: dict[str, Counter] = defaultdict(Counter)

    for t in traces:
        decision = t.get("decision", "unknown")
        intent = t.get("intent", "")
        words = tokenize(intent)
        class_words[decision].update(words)

    result = {}
    for cls, counter in sorted(class_words.items()):
        result[cls] = counter.most_common(10)
    return result


def find_confusing_traces(traces: list[dict]) -> list[dict]:
    """Find traces where heuristic decision might be wrong.

    Heuristic classifies on intent text; if there's a mismatch between
    what the heuristic would say and what was actually recorded, flag it.
    """
    confusing = []
    for t in traces:
        intent = t.get("intent", "")
        recorded = t.get("decision", "")
        heuristic = heuristic_decision(intent)
        if heuristic != recorded:
            confusing.append({
                **t,
                "heuristic_decision": heuristic,
                "mismatch": f"recorded={recorded} vs heuristic={heuristic}",
            })
    return confusing


def confusion_suggestions(traces: list[dict]) -> list[dict]:
    """Suggest traces where the heuristic decision *might* be wrong.

    Heuristic decisions that differ from the recorded decision are flagged,
    as well as cases where the heuristic is ambiguous (e.g., both code and
    research keywords present).
    """
    suggestions = []
    for t in traces:
        intent = t.get("intent", "")
        recorded = t.get("decision", "")
        heuristic = heuristic_decision(intent)
        feats = extract_features(intent)

        reasons = []

        # Mismatch between heuristic and record
        if heuristic != recorded:
            reasons.append(f"heuristic={heuristic} vs recorded={recorded}")

        # Ambiguous: both code and research keywords
        if feats["has_code_keyword"] and feats["has_research_keyword"]:
            reasons.append("ambiguous: code + research keywords")

        # Ambiguous: question with code keywords
        if feats["has_question_keyword"] and feats["has_code_keyword"]:
            reasons.append("ambiguous: question + code keywords")

        if reasons:
            suggestions.append({
                "run_id": t.get("run_id", ""),
                "intent": intent,
                "recorded_decision": recorded,
                "heuristic_decision": heuristic,
                "reasons": reasons,
                "features": feats,
            })

    return suggestions


# ── output helpers ────────────────────────────────────────────────────────────

def print_summary(traces: list[dict], word_freq: dict, confusing: list[dict]):
    """Print a summary of trace statistics."""
    total = len(traces)
    decision_counts: Counter = Counter(t.get("decision", "unknown") for t in traces)
    intent_unknown = sum(1 for t in traces if t.get("intent", "").strip() in ("", "unknown"))
    intent_known = total - intent_unknown

    print("=" * 60)
    print("ODYS Policy Trace Summary")
    print("=" * 60)
    print(f"Total traces:           {total}")
    print(f"With recorded intent:   {intent_known}")
    print(f"No intent (unknown):    {intent_unknown}")
    print()

    print("Decision breakdown:")
    for cls in sorted(DECISION_CLASSES | set(decision_counts.keys())):
        count = decision_counts.get(cls, 0)
        pct = 100.0 * count / total if total else 0
        bar = "#" * max(1, int(pct / 2)) if count else "-"
        print(f"  {cls:10s} {count:4d} ({pct:5.1f}%) {bar}")

    # Remaining class — "other" catches anything not in the known set
    other_count = total - sum(decision_counts.get(c, 0) for c in DECISION_CLASSES)
    if other_count:
        pct = 100.0 * other_count / total
        print(f"  other       {other_count:4d} ({pct:5.1f}%)")

    print()
    print("Top-10 keywords per decision class:")
    for cls in sorted(word_freq.keys()):
        if word_freq[cls]:
            words_str = ", ".join(f"{w} ({n})" for w, n in word_freq[cls])
            print(f"  [{cls}] {words_str}")

    print()
    print(f"Confusion suggestions: {len(confusing)} traces flagged")
    for c in confusing[:10]:
        print(f"  - {c.get('run_id', '?'):30s} {c.get('intent', ''):40s} "
              f"| {', '.join(c.get('reasons', []))}")
    if len(confusing) > 10:
        print(f"  ... and {len(confusing) - 10} more")
    print()


def emit_training_examples(traces: list[dict], out_path: str):
    """Write training-examples.jsonl with feature vectors."""
    count = 0
    with open(out_path, "w") as f:
        for t in traces:
            intent = t.get("intent", "")
            decision = t.get("decision", "unknown")
            feats = extract_features(intent)

            # Skip records with no meaningful intent
            if not intent.strip() or intent.strip() == "unknown":
                continue

            example = {
                "intent": intent[:500],
                "decision": decision,
                "features": {
                    "tokens": feats["tokens"],
                    "token_count": feats["token_count"],
                    "has_code_keyword": feats["has_code_keyword"],
                    "has_question_keyword": feats["has_question_keyword"],
                    "has_research_keyword": feats["has_research_keyword"],
                    "has_blocked_keyword": feats["has_blocked_keyword"],
                    "first_word": feats["first_word"],
                    "ends_with_question": feats["ends_with_question"],
                },
            }
            f.write(json.dumps(example, sort_keys=True) + "\n")
            count += 1

    print(f"Wrote {count} training examples to {out_path}")
    return count


def interactive_mode(traces: list[dict], out_path: str):
    """Interactive correction loop: show intent + predicted, ask for correction."""
    corrected = 0
    skipped = 0
    count = 0

    print("Interactive mode: for each trace, enter a|s|d|b (accept, scout, ship, direct, blocked)")
    print("  a = accept (keep recorded decision)")
    print("  s = scout  (investigate/research)")
    print("  d = direct (factual answer)")
    print("  b = blocked (missing info / can't proceed)")
    print("  q = quit")
    print()

    with open(out_path, "w") as f:
        for t in traces:
            intent = t.get("intent", "")
            decision = t.get("decision", "unknown")

            if not intent.strip() or intent.strip() == "unknown":
                skipped += 1
                continue

            count += 1
            print(f"[{count}/{len(traces)}] Intent: {intent[:100]}")
            print(f"    Recorded decision: {decision}  ", end="")

            while True:
                try:
                    key = input("> a/s/d/b/q: ").strip().lower()
                except (EOFError, KeyboardInterrupt):
                    print()
                    key = "q"

                if key == "q":
                    print("Quitting interactive mode.")
                    print(f"Processed {count} traces, corrected {corrected}, skipped {skipped}")
                    return

                if key == "a":
                    corrected_decision = decision
                    break
                elif key == "s":
                    corrected_decision = "scout"
                    corrected += 1
                    break
                elif key == "d":
                    corrected_decision = "direct"
                    corrected += 1
                    break
                elif key == "b":
                    corrected_decision = "blocked"
                    corrected += 1
                    break
                else:
                    print("    Invalid input. Options: a=accept, s=scout, d=direct, b=blocked, q=quit")

            feats = extract_features(intent)
            example = {
                "intent": intent[:500],
                "decision": corrected_decision,
                "features": {
                    "tokens": feats["tokens"],
                    "token_count": feats["token_count"],
                    "has_code_keyword": feats["has_code_keyword"],
                    "has_question_keyword": feats["has_question_keyword"],
                    "has_research_keyword": feats["has_research_keyword"],
                    "has_blocked_keyword": feats["has_blocked_keyword"],
                    "first_word": feats["first_word"],
                    "ends_with_question": feats["ends_with_question"],
                },
            }
            f.write(json.dumps(example, sort_keys=True) + "\n")

    print(f"Interactive complete: {count} processed, {corrected} corrected, {skipped} skipped")
    print(f"Corrected examples written to {out_path}")


# ── main ──────────────────────────────────────────────────────────────────────

def load_traces(traces_path: str, limit: int | None = None) -> list[dict]:
    """Load traces from JSONL file."""
    traces = []
    path = Path(traces_path)
    if not path.exists():
        print(f"WARNING: traces file not found: {traces_path}")
        return traces

    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                traces.append(json.loads(line))
            except json.JSONDecodeError as e:
                print(f"WARNING: skipping malformed line: {e}", file=sys.stderr)

    if limit is not None:
        traces = traces[:limit]

    return traces


def main():
    parser = argparse.ArgumentParser(
        description="ody-policy-train: Convert cockpit policy traces into SLM training examples."
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Limit the number of traces processed (for testing).",
    )
    parser.add_argument(
        "--interactive",
        action="store_true",
        help="Interactive mode: review each trace and correct decisions.",
    )
    parser.add_argument(
        "--state-dir",
        default=None,
        help="Override state root (default: $ODY_CREW_STATE or ~/.odysseus/cockpit).",
    )
    args = parser.parse_args()

    # Resolve state directory
    state_root = args.state_dir or os.environ.get("ODY_CREW_STATE") or os.path.expanduser("~/.odysseus/cockpit")
    traces_path = os.path.join(state_root, "policy", "traces.jsonl")
    output_dir = Path(__file__).parent.resolve()
    examples_path = str(output_dir / "training-examples.jsonl")
    corrected_path = str(output_dir / "training-examples-corrected.jsonl")

    # Load traces
    traces = load_traces(traces_path, args.limit)
    if not traces:
        print(f"No traces found at {traces_path}")
        print("Nothing to analyze. Collect traces via:")
        print("  ody-policy record <run_id>")
        print(f"  (reads from {state_root}/runs/<run_id>/)")
        sys.exit(0)

    # Analysis
    wf = word_frequency(traces)
    confusing = confusion_suggestions(traces)

    # Print summary
    print_summary(traces, wf, confusing)

    # Emit training examples
    count = emit_training_examples(traces, examples_path)

    # Interactive mode
    if args.interactive:
        interactive_mode(traces, corrected_path)
    else:
        print(f"Use --interactive to review and correct decisions")
        print(f"Training examples: {examples_path}")

    print()
    print("=" * 60)
    print("Next steps for data collection:")
    print("1. Every cockpit spawn should record (intent, decision, outcome)")
    print("2. Target: 500+ traces before first SLM training attempt")
    print("3. Use `--interactive` to build a correction corpus")
    print("4. Train a lightweight classifier (MiniMax-M3 via tokenrouter)")

    return count


if __name__ == "__main__":
    main()
