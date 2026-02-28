from pydantic import BaseModel


class CounterResponse(BaseModel):
    count: int
