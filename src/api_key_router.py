from typing import Optional, List


class ApiKeyRouter:
    def __init__(self, keys: Optional[List[str]] = None) -> None:
        self._keys = list(keys) if keys is not None else []
        self._index = 0
        self._quota_exceeded = set()

    def mark_quota_error(self, key: str) -> None:
        self._quota_exceeded.add(key)

    def available_keys(self) -> list:
        return [k for k in self._keys if k not in self._quota_exceeded]

    def is_available(self, key: str) -> bool:
        return key in self._keys and key not in self._quota_exceeded

    @staticmethod
    def is_quota_error(exc: BaseException) -> bool:
        message = str(exc).lower()
        type_name = type(exc).__name__.lower()
        indicators = ("quota", "rate limit", "429", "resource_exhausted")
        for indicator in indicators:
            if indicator in message or indicator in type_name:
                return True
        return False


if __name__ == "__main__":
    # Spec tests
    assert ApiKeyRouter.is_quota_error(Exception('429 quota exceeded')) is True
    assert ApiKeyRouter.is_quota_error(Exception('rate limit reached for requests')) is True
    assert ApiKeyRouter.is_quota_error(ValueError('bad input')) is False

    # Existing tests
    r = ApiKeyRouter(["a", "b", "c"])
    assert r._keys == ["a", "b", "c"] and r._index == 0

    r = ApiKeyRouter()
    assert r._keys == [] and r._quota_exceeded == set()

    r = ApiKeyRouter(["x"])
    assert r.is_available("x") is True

    r = ApiKeyRouter([])
    assert r.is_quota_error(Exception('quota exceeded')) == True
    r = ApiKeyRouter([])
    assert r.is_quota_error(Exception('rate limit hit')) == True
    r = ApiKeyRouter([])
    assert r.is_quota_error(Exception('connection refused')) == False
    r = ApiKeyRouter(['a', 'b', 'c']); assert sorted(r.available_keys()) == ['a', 'b', 'c']
    r = ApiKeyRouter(['a', 'b', 'c']); r.mark_quota_error('b'); assert sorted(r.available_keys()) == ['a', 'c']
