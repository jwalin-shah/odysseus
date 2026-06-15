import datetime


def build_approval_record(owner: str, action: str, decision: str, reason: str = '') -> dict:
    return {
        'owner': owner,
        'action': action,
        'decision': decision,
        'reason': reason,
        'timestamp': datetime.datetime.now().isoformat(),
    }
