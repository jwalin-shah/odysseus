package agentloop

// DetectRunawayCall returns the tool name of a call signature that has been
// repeated >= threshold times. Returns "" (empty string) when no signature is
// at or above the threshold.
//
// This is the Go port of Python's _detect_runaway_call. The Python version
// returns None on no-runaway; the Go version returns "" for the same case
// (empty string tests as falsy).
//
// callFreq keys are "{tool_type}:{content[:120]}" — e.g.
// "manage_calendar:{\"action\":\"list_events\"}". The function compares the
// COUNT for each key against threshold; it does not look at distinct-key
// counts. This matches the Python Counter-based implementation, which counts
// identical repeated calls (same tool AND same args), so a legitimate batch
// of distinct calls to one tool (e.g. 18 different create_event calls) is
// NOT flagged.
//
// threshold defaults to 15 (Python's _detect_runaway_call default).
func DetectRunawayCall(callFreq map[string]int, threshold int) string {
	if threshold <= 0 {
		threshold = 15
	}
	for sig, n := range callFreq {
		if n >= threshold {
			// Strip the ":content[:120]" suffix to recover the bare tool name.
			for i := 0; i < len(sig); i++ {
				if sig[i] == ':' {
					return sig[:i]
				}
			}
			return sig
		}
	}
	return ""
}
