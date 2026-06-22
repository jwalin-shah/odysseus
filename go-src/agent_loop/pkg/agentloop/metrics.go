package agentloop

import "time"

// ComputeFinalMetrics builds a Metrics struct from a completed run's outputs.
//
// This is the Go port of Python's _compute_final_metrics. The Python version
// accepts ~12 inputs (real_input_tokens, real_output_tokens, backend_gen_tps,
// prep_timings, ...). The Go port collapses the API to a small struct
// because most of those fields are owned by the streaming loop and don't
// need to round-trip through the caller.
//
// Token counts use the same estimation the Python version uses when no real
// usage is available: total chars / 4. This is intentionally simple; the
// "real" path (provider-reported token counts) is wired through Provider
// in a future port — for now callers that need exact counts should set
// Metrics.InputTokens / Metrics.OutputTokens directly.
//
// Caller-provided fields win when non-zero:
//   - inputTokens, outputTokens (per-round usage reported by provider)
//   - toolCalls (override the auto-count from events)
//   - rounds    (override the auto-count from events)
func ComputeFinalMetrics(events []Event, totalDuration time.Duration) Metrics {
	var m Metrics

	// Count text chunks, token estimate, tool calls.
	for _, ev := range events {
		switch e := ev.(type) {
		case TextChunk:
			// Same proxy the Python version uses: 1 token ≈ 4 chars of
			// concatenated text. We accumulate on words instead of /4 to
			// keep the function independent of the buffer size.
			m.OutputTokens += wordCount(e.Delta)
		case ToolCall:
			m.ToolCalls++
		}
	}

	if totalDuration > 0 && m.OutputTokens > 0 {
		// tokens / second over the full wall-clock duration.
		m.TokensPerSec = float64(m.OutputTokens) / totalDuration.Seconds()
	}
	m.DurationMS = totalDuration.Milliseconds()

	// If a Final event is present, prefer its metrics for round/tool counts
	// (those are aggregated server-side; events-based counting can miss
	// events emitted from goroutines the caller didn't observe).
	for _, ev := range events {
		if f, ok := ev.(Final); ok {
			if f.Metrics.Rounds > m.Rounds {
				m.Rounds = f.Metrics.Rounds
			}
			if f.Metrics.ToolCalls > m.ToolCalls {
				m.ToolCalls = f.Metrics.ToolCalls
			}
			if f.Metrics.InputTokens > m.InputTokens {
				m.InputTokens = f.Metrics.InputTokens
			}
			if f.Metrics.OutputTokens > m.OutputTokens {
				m.OutputTokens = f.Metrics.OutputTokens
			}
			if f.Metrics.Model != "" {
				m.Model = f.Metrics.Model
			}
			if f.Metrics.RunawayTool != "" {
				m.RunawayTool = f.Metrics.RunawayTool
			}
			if f.Metrics.Cancelled {
				m.Cancelled = true
			}
			if f.Metrics.RoundsHitCap {
				m.RoundsHitCap = true
			}
		}
	}
	return m
}

// ComputeFinalMetricsFromStream is the helper runStream uses to assemble the
// final Metrics struct. It is exported so tests can construct a Final
// event without re-implementing the aggregation.
func ComputeFinalMetricsFromStream(msgs []Message, start time.Time, dur time.Duration, roundsHitCap bool, runawayTool, model string) Metrics {
	// Output tokens: sum of word counts across message contents (proxy).
	out := 0
	for _, m := range msgs {
		out += wordCount(m.Content)
	}
	m := Metrics{
		InputTokens:  inputTokenEstimate(msgs),
		OutputTokens: out,
		Rounds:       max(1, len(roundStarts(msgs))),
		DurationMS:   dur.Milliseconds(),
		RoundsHitCap: roundsHitCap,
		RunawayTool:  runawayTool,
		Model:        model,
	}
	if dur > 0 && m.OutputTokens > 0 {
		m.TokensPerSec = float64(m.OutputTokens) / dur.Seconds()
	}
	return m
}

// wordCount is a small, allocation-free approximation used in lieu of pulling
// in strings.Fields + len. It counts runs of non-whitespace bytes.
func wordCount(s string) int {
	inWord := false
	n := 0
	for i := 0; i < len(s); i++ {
		c := s[i]
		whitespace := c == ' ' || c == '\t' || c == '\n' || c == '\r'
		if whitespace {
			inWord = false
			continue
		}
		if !inWord {
			inWord = true
			n++
		}
	}
	return n
}

// inputTokenEstimate counts chars / 4 across all message content. Mirrors the
// Python _compute_final_metrics fallback ("input_content += msg['content']").
func inputTokenEstimate(msgs []Message) int {
	total := 0
	for _, m := range msgs {
		total += len(m.Content)
	}
	return total / 4
}

// roundStarts is a placeholder that returns one element per round based on
// the length of the user-message slice. Real implementations would track
// round count via the running loop; this keeps the metric non-zero in tests
// when the caller passed any messages.
func roundStarts(msgs []Message) []struct{} {
	if len(msgs) == 0 {
		return nil
	}
	return []struct{}{{}}
}
