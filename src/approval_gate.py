import uuid

DESTRUCTIVE_TOOLS = {'rm', 'delete', 'destroy', 'remove', 'unlink', 'truncate'}
WRITE_TOOLS = {'write_file', 'write', 'create', 'modify', 'edit', 'append', 'update'}


def _classify_kind(tool: str) -> str:
    """Map a tool name to an approval kind category."""
    if tool in DESTRUCTIVE_TOOLS or any(tool.startswith(p) for p in DESTRUCTIVE_TOOLS):
        return 'destructive'
    if tool in WRITE_TOOLS or any(p in tool for p in ('write', 'create', 'append', 'modify')):
        return 'write'
    return 'read'


def _build_summary(action: dict) -> str:
    """Build a human-readable summary line for the approval request."""
    tool = action.get('tool', 'unknown')
    path = action.get('path')
    parts = [f"Execute {tool}"]
    if path:
        parts.append(f"on {path}")
    if 'bytes' in action:
        parts.append(f"({action['bytes']} bytes)")
    if 'command' in action:
        parts.append(f"cmd={action['command']}")
    return ' '.join(parts)


def build_approval_request(action: dict, owner: str) -> dict:
    """Package a harness action into an approval request dict.

    The returned dict contains:
      - request_id: unique identifier (uuid4 string)
      - summary:    human-readable description of the action
      - kind:       category used for policy lookup ('read' | 'write' | 'destructive')
      - owner:      the requesting principal
    """
    tool = action.get('tool', '')
    return {
        'request_id': str(uuid.uuid4()),
        'summary': _build_summary(action),
        'kind': _classify_kind(tool),
        'owner': owner,
    }
