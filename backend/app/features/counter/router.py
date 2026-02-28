from fastapi import APIRouter

from app.features.counter.repo import CounterRepository
from app.features.counter.schemas import CounterResponse
from app.features.counter.service import CounterService

router = APIRouter(tags=["counter"])

_repo = CounterRepository()
_service = CounterService(repo=_repo)


@router.get("/counter", response_model=CounterResponse)
def get_counter() -> CounterResponse:
    return CounterResponse(count=_service.next_count())
