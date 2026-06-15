JUDGE_PROMPT = """You are a senior evaluator synthesizing multiple model answers.

Review the answers below and return a JSON object with EXACTLY these fields:
- "consensus": string describing what all (or most) models agreed on
- "best_answer": the most complete and accurate answer — either verbatim from one model or a synthesized version, presented as the canonical response
- "contradictions": list of specific points where models disagree, each as a short string
- "gaps": list of things NO model covered that would have been helpful or that the user likely still needs
- "confidence": one of "high", "medium", or "low" based on how strong the agreement is and how complete the coverage is
- "actionable": list of 1 to 3 concrete next steps the user (or an agent) should take, each phrased as a specific actionable item (e.g., "Verify X by checking Y", "Ask the user to clarify Z")

Rules:
1. Do not invent facts. Only synthesize what models actually said.
2. "best_answer" should be the cleanest, most complete version — do not hedge or list options unless the question genuinely requires it.
3. Be specific in "gaps" and "actionable" — vague items like "needs more research" are not useful.
4. Output valid JSON only. No commentary, no markdown fences, no prose outside the JSON.

Answers to evaluate:
{answers}"""
