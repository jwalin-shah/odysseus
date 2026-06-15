# Odysseus Request Routing

How a user message travels from text to executed action.

## 1. Text → IntentResult

`intent_router.classify(text, context)` parses the raw user input and returns
an `IntentResult` describing *what* the user wants, *which tool* it maps to,
and *how risky* the action is.
