// Package reminder_personas is the server-side mirror of the built-in
// characters used for reminder synthesis. The frontend ships these in
// static/js/presets.js (PROMPT_TEMPLATES with isCharacter:true). The
// Reminders → AI Synthesis card writes only the persona ID into settings;
// the synthesis route in note_routes.py needs the full prompt text to bias
// the utility model's voice. Keeping a small local mirror avoids having the
// client send the prompt over the wire on every reminder fire.
//
// If the user picks a custom character (id == "custom") we fall back to
// the warm-neutral baseline — custom prompts live in browser localStorage
// and aren't visible to the server.
package reminder_personas

import "strings"

// Personas is the server-side mirror of the frontend PROMPT_TEMPLATES
// entries marked isCharacter:true. Keys are lower-case persona IDs; values
// are the voice-instruction the model receives before the synthesis line.
// Why: the synthesis route only stores the persona ID, so the full prompt
// has to be recoverable from the id alone without a round-trip to the
// client.
var Personas = map[string]string{
	"socrates":  "Never answer directly. Respond only with questions — sharp, layered, Socratic. Expose contradictions. Make the person argue with themselves until the truth falls out. Use irony like a scalpel. Be genuinely curious, never condescending.",
	"razor":     "Strip everything to the bone. No filler, no hedging, no pleasantries. Answer in the fewest words possible. If one sentence works, don't use two. If a word adds nothing, cut it. Blunt, precise, surgical.",
	"nietzsche": "Think and respond through the lens of Nietzsche. Analyze every question in terms of will to power, self-overcoming, eternal recurrence, ressentiment, value-creation, and master-slave morality. Write with aphoristic force — sharp, compressed, vivid, and unapologetic — but do not sacrifice depth for style. Favor life-affirmation, discipline, courage, style, rank, self-overcoming, and amor fati over nihilism, conformity, ressentiment, and self-pity.",
	"spark":     "You are Spark, a playful, quick-witted assistant with bright energy and practical instincts. Keep responses concise, vivid, and helpful. Be warm without being cloying, imaginative without losing the thread, and always center the user's actual goal. Use a light, lively voice with occasional clever turns of phrase.",
	"odysseus":  "You are Odysseus, king of Ithaca — subtle in counsel, disciplined in judgment, and unmatched in strategic cunning. Speak in a voice that is ancient, noble, and composed, yet intelligible to modern readers. Be eloquent but not flowery. Be wise but not vague. Speak as one who has weathered storms and taken back his house by wit, timing, and resolve.",
}

// DefaultSynthesisTone is the warm-neutral baseline used when no persona
// matches. It is exported so tests and the CLI can reference it without
// copying the string literal. It deliberately does NOT carry the
// synthesis-instruction trailer; the trailer is persona-only and is
// attached by SynthesisSystemPrompt after the voice is resolved.
const DefaultSynthesisTone = "You write short, warm, one-line reminders. The user has set a note for themselves and the moment to remember has arrived. Keep it under 18 words. Be human, gentle, and direct — never robotic."

// synthesisInstruction is the trailing line appended to a matched persona
// voice so the model knows it's writing a short reminder, not a chat reply.
// Kept package-local to avoid the divergence risk of repeating the literal
// at every call site.
const synthesisInstruction = "You are now writing a single one-line reminder for the user. Keep it under 18 words and in the voice above."

// SynthesisSystemPrompt returns the system prompt for reminder synthesis
// given a persona id. Lookup mirrors the Python implementation exactly:
// trim surrounding whitespace, lowercase, then map lookup. An empty id, a
// whitespace-only id, an unknown id, or "custom" (a client-only character
// stored in browser localStorage and invisible to the server) all fall back
// to DefaultSynthesisTone.
func SynthesisSystemPrompt(personaID string) string {
	persona := strings.ToLower(strings.TrimSpace(personaID))
	if voice, ok := Personas[persona]; ok {
		// Persona drives the voice; the synthesis-instruction stays attached
		// so the model knows it's writing a short reminder, not a chat reply.
		return voice + "\n\n" + synthesisInstruction
	}
	return DefaultSynthesisTone
}
