JUDGE_PROMPT = """You are a judge evaluating answers from multiple AI models to the same question.

Question: {question}

Model answers:
{answers}

Analyze the answers and respond with ONLY a JSON object (no prose, no markdown) using this exact schema:

{{
  "consensus": "A 1-3 sentence summary of what all (or most) models agreed on. If there is no real agreement, say 'No strong consensus' and briefly note the most common thread.",
  "best_answer": "The single most complete and accurate answer, either copied verbatim from one model or tightly synthesized from several. Should directly answer the question.",
  "contradictions": ["Specific, concrete disagreements between models. Each entry should be a short statement (e.g., 'Model A says X, Model B says Y'). Empty list [] if none."],
  "gaps": ["Things no model covered well that a user would likely want to know. Be specific and concrete (e.g., 'No model addressed error handling for empty inputs'). Empty list [] if coverage was thorough."],
  "confidence": "high | medium | low — high if models strongly agree and coverage is solid, medium if some disagreement or gaps, low if major contradictions or missing critical information.",
  "actionable": ["1-3 concrete next steps, follow-up questions, or direct answers the user can act on. Prefer specific, usable output over generic advice."]
}}

Rules:
- Do NOT rank or score the models. Avoid phrases like 'Model A was best' — just give the best answer directly.
- Do NOT invent information not present in the models' answers when writing best_answer or consensus.
- Be concise. Each string field should be 1-3 sentences. Array entries should be short.
- Output ONLY the JSON object. No preamble, no explanation, no code fences."""
