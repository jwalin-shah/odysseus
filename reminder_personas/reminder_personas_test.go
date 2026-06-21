package reminder_personas

import (
	"sort"
	"strings"
	"testing"
)

func TestSynthesisSystemPrompt_KnownPersonas(t *testing.T) {
	cases := []struct {
		id   string
		want string
	}{
		{
			id: "socrates",
			want: "Never answer directly. Respond only with questions — sharp, layered, Socratic. Expose contradictions. Make the person argue with themselves until the truth falls out. Use irony like a scalpel. Be genuinely curious, never condescending." +
				"\n\n" +
				"You are now writing a single one-line reminder for the user. Keep it under 18 words and in the voice above.",
		},
		{
			id: "razor",
			want: "Strip everything to the bone. No filler, no hedging, no pleasantries. Answer in the fewest words possible. If one sentence works, don't use two. If a word adds nothing, cut it. Blunt, precise, surgical." +
				"\n\n" +
				"You are now writing a single one-line reminder for the user. Keep it under 18 words and in the voice above.",
		},
		{
			id: "nietzsche",
			want: "Think and respond through the lens of Nietzsche. Analyze every question in terms of will to power, self-overcoming, eternal recurrence, ressentiment, value-creation, and master-slave morality. Write with aphoristic force — sharp, compressed, vivid, and unapologetic — but do not sacrifice depth for style. Favor life-affirmation, discipline, courage, style, rank, self-overcoming, and amor fati over nihilism, conformity, ressentiment, and self-pity." +
				"\n\n" +
				"You are now writing a single one-line reminder for the user. Keep it under 18 words and in the voice above.",
		},
		{
			id: "spark",
			want: "You are Spark, a playful, quick-witted assistant with bright energy and practical instincts. Keep responses concise, vivid, and helpful. Be warm without being cloying, imaginative without losing the thread, and always center the user's actual goal. Use a light, lively voice with occasional clever turns of phrase." +
				"\n\n" +
				"You are now writing a single one-line reminder for the user. Keep it under 18 words and in the voice above.",
		},
		{
			id: "odysseus",
			want: "You are Odysseus, king of Ithaca — subtle in counsel, disciplined in judgment, and unmatched in strategic cunning. Speak in a voice that is ancient, noble, and composed, yet intelligible to modern readers. Be eloquent but not flowery. Be wise but not vague. Speak as one who has weathered storms and taken back his house by wit, timing, and resolve." +
				"\n\n" +
				"You are now writing a single one-line reminder for the user. Keep it under 18 words and in the voice above.",
		},
	}
	for _, tc := range cases {
		t.Run(tc.id, func(t *testing.T) {
			got := SynthesisSystemPrompt(tc.id)
			if got != tc.want {
				t.Errorf("SynthesisSystemPrompt(%q) mismatch:\n got: %q\nwant: %q", tc.id, got, tc.want)
			}
			// Belt-and-suspenders: every known persona must include the
			// persona-specific voice AND the trailing synthesis line,
			// otherwise the model would treat the reminder as a chat reply.
			if !strings.Contains(got, Personas[tc.id]) {
				t.Errorf("persona %q output missing its own voice text", tc.id)
			}
			if !strings.HasSuffix(got, "Keep it under 18 words and in the voice above.") {
				t.Errorf("persona %q output missing trailing synthesis instruction", tc.id)
			}
		})
	}
}

func TestSynthesisSystemPrompt_EmptyFallsBack(t *testing.T) {
	got := SynthesisSystemPrompt("")
	if got != DefaultSynthesisTone {
		t.Errorf("empty id should fall back to DefaultSynthesisTone\ngot:  %q\nwant: %q", got, DefaultSynthesisTone)
	}
}

func TestSynthesisSystemPrompt_WhitespaceOnlyFallsBack(t *testing.T) {
	for _, in := range []string{" ", "   ", "\t", "\n", " \t \n "} {
		t.Run("ws="+in, func(t *testing.T) {
			got := SynthesisSystemPrompt(in)
			if got != DefaultSynthesisTone {
				t.Errorf("whitespace id %q should fall back to DefaultSynthesisTone\ngot:  %q", in, got)
			}
		})
	}
}

func TestSynthesisSystemPrompt_CustomFallsBack(t *testing.T) {
	// "custom" lives in browser localStorage on the client and is not
	// visible to the server — the docstring is explicit that we fall back
	// to the warm-neutral baseline. Cover case-insensitive variants too,
	// since the spec only resolves to a persona on the lowercased key.
	for _, in := range []string{"custom", "Custom", "CUSTOM", "cUsToM"} {
		t.Run("case="+in, func(t *testing.T) {
			got := SynthesisSystemPrompt(in)
			if got != DefaultSynthesisTone {
				t.Errorf("custom id %q should fall back to DefaultSynthesisTone\ngot:  %q", in, got)
			}
		})
	}
}

func TestSynthesisSystemPrompt_UnknownFallsBack(t *testing.T) {
	for _, in := range []string{"therapist", "made-up", "plato", "persona-xyz", "totally-not-a-persona"} {
		t.Run("id="+in, func(t *testing.T) {
			got := SynthesisSystemPrompt(in)
			if got != DefaultSynthesisTone {
				t.Errorf("unknown id %q should fall back to DefaultSynthesisTone\ngot:  %q", in, got)
			}
		})
	}
}

func TestSynthesisSystemPrompt_WhitespacePaddedKnownFindsPersona(t *testing.T) {
	// Python uses (persona_id or "").strip().lower(); the same TrimSpace +
	// ToLower here must still resolve to the persona voice.
	got := SynthesisSystemPrompt("  SOCRATES  ")
	want := Personas["socrates"] + "\n\n" +
		"You are now writing a single one-line reminder for the user. Keep it under 18 words and in the voice above."
	if got != want {
		t.Errorf("padded known id mismatch:\n got: %q\nwant: %q", got, want)
	}
}

func TestDefaultSynthesisTone_OmitsTrailer(t *testing.T) {
	// The trailer must be persona-only; if it ever leaks into the default
	// tone we'd be changing the model instructions for the empty/unknown
	// branch in a way the spec calls out as wrong.
	if strings.Contains(DefaultSynthesisTone, "in the voice above") {
		t.Errorf("DefaultSynthesisTone should not contain the persona trailer\ngot: %q", DefaultSynthesisTone)
	}
}

func TestPersonas_AllCanonicalIDsPresent(t *testing.T) {
	// Guards against an accidental deletion in the map. Keep this list in
	// sync with the frontend PROMPT_TEMPLATES isCharacter:true set.
	for _, id := range []string{"socrates", "razor", "nietzsche", "spark", "odysseus"} {
		if _, ok := Personas[id]; !ok {
			t.Errorf("Personas missing canonical id %q", id)
		}
	}
}

func TestPersonas_AllKeysNonEmpty(t *testing.T) {
	// Defensive: a blank voice would still parse fine but would silently
	// degrade reminder quality. Catch that at unit-test time.
	for id, voice := range Personas {
		if strings.TrimSpace(voice) == "" {
			t.Errorf("Personas[%q] has empty voice text", id)
		}
	}
}

func TestPersonas_KeysAreSortedForStableCLI(t *testing.T) {
	// The --list CLI output should be deterministic. The Go map iteration
	// order is randomized, so callers must sort before printing. This
	// guards the CLI helper by asserting the canonical set is a known
	// sorted ordering.
	ids := make([]string, 0, len(Personas))
	for id := range Personas {
		ids = append(ids, id)
	}
	sort.Strings(ids)
	want := []string{"nietzsche", "odysseus", "razor", "socrates", "spark"}
	if len(ids) != len(want) {
		t.Fatalf("Personas has %d keys, want %d", len(ids), len(want))
	}
	for i := range want {
		if ids[i] != want[i] {
			t.Errorf("sorted Personas mismatch at %d: got %q, want %q", i, ids[i], want[i])
		}
	}
}
