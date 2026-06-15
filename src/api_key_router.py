from typing import List, Set


class ApiKeyRouter:
    def __init__(self, keys: List[str]) -> None:
        self._keys: List[str] = list(keys)
        self._exhausted: Set[str] = set()

    def report_quota_error(self, key: str) -> None:
        if key in self._keys:
            self._exhausted.add(key)

    def stats(self) -> dict:
        total = len(self._keys)
        exhausted = len(self._exhausted)
        available = total - exhausted
        return {
            'total': total,
            'available': available,
            'exhausted': exhausted,
            'keys': list(self._keys)
        }
