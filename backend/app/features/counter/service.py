from app.features.counter.repo import CounterRepository


class CounterService:
    def __init__(self, repo: CounterRepository) -> None:
        self._repo = repo

    def next_count(self) -> int:
        return self._repo.increment_and_get()
