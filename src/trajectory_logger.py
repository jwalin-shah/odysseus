import copy
from typing import List, Optional, Any


class TrajectoryStep:
    def __init__(self, role: str, content: str, tool_calls: Optional[List[dict]] = None):
        self.role = role
        self.content = content
        self.tool_calls = tool_calls if tool_calls is not None else []


def build_trajectory_step(role: str, content: str, tool_calls: Optional[List[dict]] = None) -> TrajectoryStep:
    return TrajectoryStep(role, content, tool_calls)


def _redact_string(text: str, secrets: list) -> str:
    for secret in secrets:
        if secret and isinstance(secret, str):
            text = text.replace(secret, '[REDACTED]')
    return text


def _redact_value(value: Any, secrets: list) -> Any:
    if isinstance(value, str):
        return _redact_string(value, secrets)
    elif isinstance(value, dict):
        return {k: _redact_value(v, secrets) for k, v in value.items()}
    elif isinstance(value, list):
        return [_redact_value(item, secrets) for item in value]
    return value


def redact_secrets_in_step(step: TrajectoryStep, secrets: list) -> TrajectoryStep:
    new_step = copy.deepcopy(step)
    new_step.content = _redact_string(new_step.content, secrets)
    if hasattr(new_step, 'tool_calls') and new_step.tool_calls:
        for i, tool_call in enumerate(new_step.tool_calls):
            if isinstance(tool_call, dict) and 'args' in tool_call:
                new_step.tool_calls[i]['args'] = _redact_value(tool_call['args'], secrets)
    return new_step
