from typing import Dict, Any, Optional
from src.tool_registry import odysseus_tool
from src.tool_implementations import (
    do_create_document,
    do_update_document,
    do_edit_document,
    do_suggest_document,
)
from src.tool_execution import _do_edit_file

READ_FILE_SCHEMA = {
    "type": "function",
    "function": {
        "name": "read_file",
        "description": "Read a file from disk. Optionally read a line range with offset/limit for large files.",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "File path to read"},
                "offset": {"type": "integer", "description": "1-based line to start reading from (optional)"},
                "limit": {"type": "integer", "description": "Max number of lines to read from offset (optional)"}
            },
            "required": ["path"]
        }
    }
}

GREP_SCHEMA = {
    "type": "function",
    "function": {
        "name": "grep",
        "description": "Search file contents for a regular expression across a directory tree (uses ripgrep when available, respecting .gitignore). Returns file:line:match. PREFER this over `bash grep/rg` for code search — confined to the allowed roots, structured output.",
        "parameters": {
            "type": "object",
            "properties": {
                "pattern": {"type": "string", "description": "Regular expression to search for"},
                "path": {"type": "string", "description": "Directory or file to search (optional; defaults to the project root)"},
                "glob": {"type": "string", "description": "Only search files matching this glob, e.g. '*.py' (optional)"},
                "ignore_case": {"type": "boolean", "description": "Case-insensitive match (optional)"},
                "max_results": {"type": "integer", "description": "Max matches to return (optional)"}
            },
            "required": ["pattern"]
        }
    }
}

GLOB_SCHEMA = {
    "type": "function",
    "function": {
        "name": "glob",
        "description": "Find files by glob pattern (recursive), newest first. e.g. '**/*.py'. PREFER this over `bash find/ls` for locating files — confined to the allowed roots.",
        "parameters": {
            "type": "object",
            "properties": {
                "pattern": {"type": "string", "description": "Glob pattern, e.g. '**/*.ts' or 'src/**/test_*.py'"},
                "path": {"type": "string", "description": "Base directory (optional; defaults to the project root)"}
            },
            "required": ["pattern"]
        }
    }
}

LS_SCHEMA = {
    "type": "function",
    "function": {
        "name": "ls",
        "description": "List the entries of a directory (folders first, then files with sizes). PREFER this over `bash ls` — confined to the allowed roots.",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Directory to list (optional; defaults to the project root)"}
            },
            "required": []
        }
    }
}

WRITE_FILE_SCHEMA = {
    "type": "function",
    "function": {
        "name": "write_file",
        "description": "Write/save a file to disk",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "File path to write to"},
                "content": {"type": "string", "description": "File content to write"}
            },
            "required": ["path", "content"]
        }
    }
}

EDIT_FILE_SCHEMA = {
    "type": "function",
    "function": {
        "name": "edit_file",
        "description": "Edit a file ON DISK by exact string replacement (home folder, project files, any real path like ~/sweden.txt or /path/to/file). This is the right tool for files on disk — NOT edit_document (that's for editor-panel documents). PREFER this over bash (sed/echo) — it shows a diff. old_string must match the file exactly and be unique (or set replace_all). Use write_file to create a new file.",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "File path to edit"},
                "old_string": {"type": "string", "description": "Exact text to replace (must match the file, including indentation)"},
                "new_string": {"type": "string", "description": "Replacement text"},
                "replace_all": {"type": "boolean", "description": "Replace all occurrences instead of requiring a unique match"}
            },
            "required": ["path", "old_string", "new_string"]
        }
    }
}

CREATE_DOCUMENT_SCHEMA = {
    "type": "function",
    "function": {
        "name": "create_document",
        "description": "Create a new document in the editor panel. Use this when the user asks to write, create, build, or generate code, scripts, programs, games, apps, or any substantial content (>15 lines) AND there is no already-open document/email draft that the request refers to. If an email compose draft is open, edit that draft instead of creating another document. NEVER put large code blocks directly in chat — use this tool instead.",
        "parameters": {
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "Document title"},
                "language": {"type": "string", "description": "Programming language or format (e.g. python, javascript, markdown, text)"},
                "content": {"type": "string", "description": "The document content"}
            },
            "required": ["title", "content"]
        }
    }
}

EDIT_DOCUMENT_SCHEMA = {
    "type": "function",
    "function": {
        "name": "edit_document",
        "description": "Edit a document OPEN IN THE EDITOR PANEL (created via create_document) — NOT a file on disk. For files on disk (home folder, project files, anything with a path like ~/x.txt or /path/to/file) use edit_file instead. Targeted find-and-replace with multiple FIND/REPLACE pairs per call; use for any edit smaller than a full rewrite. Do NOT send the whole file back via update_document for small edits.",
        "parameters": {
            "type": "object",
            "properties": {
                "edits": {
                    "type": "array",
                    "description": "List of find/replace edits (first match only per edit)",
                    "items": {
                        "type": "object",
                        "properties": {
                            "find": {"type": "string", "description": "Exact text to find in the document"},
                            "replace": {"type": "string", "description": "Text to replace it with"}
                        },
                        "required": ["find", "replace"]
                    }
                }
            },
            "required": ["edits"]
        }
    }
}

SUGGEST_DOCUMENT_SCHEMA = {
    "type": "function",
    "function": {
        "name": "suggest_document",
        "description": "Suggest improvements to the active document WITHOUT editing it. Creates inline comment bubbles the user can accept or reject. Use when the user asks for suggestions, review, improvements, or feedback.",
        "parameters": {
            "type": "object",
            "properties": {
                "suggestions": {
                    "type": "array",
                    "description": "List of suggested changes with reasons",
                    "items": {
                        "type": "object",
                        "properties": {
                            "find": {"type": "string", "description": "Exact text in the document to suggest changing"},
                            "replace": {"type": "string", "description": "Suggested replacement text"},
                            "reason": {"type": "string", "description": "Brief explanation of why this change helps"}
                        },
                        "required": ["find", "replace", "reason"]
                    }
                }
            },
            "required": ["suggestions"]
        }
    }
}

UPDATE_DOCUMENT_SCHEMA = {
    "type": "function",
    "function": {
        "name": "update_document",
        "description": "Replace the ENTIRE active document. ONLY use for genuine full rewrites (>50% of lines changed). For any smaller change, use edit_document — echoing back the whole file for small edits is wasteful.",
        "parameters": {
            "type": "object",
            "properties": {
                "content": {"type": "string", "description": "Complete new document content"}
            },
            "required": ["content"]
        }
    }
}

@odysseus_tool(READ_FILE_SCHEMA)
async def read_file(*args, **kwargs):
    pass

@odysseus_tool(GREP_SCHEMA)
async def grep(*args, **kwargs):
    pass

@odysseus_tool(GLOB_SCHEMA)
async def glob(*args, **kwargs):
    pass

@odysseus_tool(LS_SCHEMA)
async def ls(*args, **kwargs):
    pass

@odysseus_tool(WRITE_FILE_SCHEMA)
async def write_file(*args, **kwargs):
    pass

@odysseus_tool(EDIT_FILE_SCHEMA)
async def edit_file(*args, **kwargs):
    return await _do_edit_file(*args, **kwargs)

@odysseus_tool(CREATE_DOCUMENT_SCHEMA)
async def create_document(*args, **kwargs):
    return await do_create_document(*args, **kwargs)

@odysseus_tool(EDIT_DOCUMENT_SCHEMA)
async def edit_document(*args, **kwargs):
    return await do_edit_document(*args, **kwargs)

@odysseus_tool(SUGGEST_DOCUMENT_SCHEMA)
async def suggest_document(*args, **kwargs):
    return await do_suggest_document(*args, **kwargs)

@odysseus_tool(UPDATE_DOCUMENT_SCHEMA)
async def update_document(*args, **kwargs):
    return await do_update_document(*args, **kwargs)
