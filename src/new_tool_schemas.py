"""Schema definitions for the new Odysseus agent tools: inbox_read and inbox_send."""

NEW_TOOL_SCHEMAS = [
    {
        "name": "inbox_read",
        "description": "Read messages, contacts, or calendar from any platform",
        "input_schema": {
            "type": "object",
            "properties": {
                "platform": {
                    "type": "string",
                    "enum": ["imessage", "gmail", "whatsapp", "calendar", "linkedin"],
                },
                "action": {
                    "type": "string",
                    "enum": ["contacts", "thread", "unread", "upcoming", "dms"],
                },
                "contact": {"type": "string"},
                "limit": {"type": "integer", "default": 10},
            },
            "required": ["platform", "action"],
        },
    },
    {
        "name": "inbox_send",
        "description": "Send a message via imessage, whatsapp, or gmail (always requires human approval before sending)",
        "input_schema": {
            "type": "object",
            "properties": {
                "to": {"type": "string"},
                "body": {"type": "string"},
                "platform": {
                    "type": "string",
                    "enum": ["imessage", "whatsapp", "gmail"],
                },
                "subject": {"type": "string"},
            },
            "required": ["to", "body", "platform"],
        },
    },
]
