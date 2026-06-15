import json
import datetime

_configured_stream = None

def configure_logger(stream):
    global _configured_stream
    _configured_stream = stream

def log_event(level: str, event: str, **fields) -> str:
    record = {
        'level': level.upper(),
        'event': event,
        'timestamp': datetime.datetime.utcnow().isoformat() + 'Z',
    }
    record.update(fields)
    line = json.dumps(record) + '\n'
    _configured_stream.write(line)
    return line
