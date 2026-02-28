from threading import Lock

# Process-wide in-memory state protected by Lock for thread-safe increments.
_count = 0
_lock = Lock()


class CounterRepository:
    def increment_and_get(self) -> int:
        global _count
        with _lock:
            _count += 1
            return _count
