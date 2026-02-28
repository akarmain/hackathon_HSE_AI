from fastapi.testclient import TestClient

from app.main import create_app


def test_counter_increments_globally() -> None:
    client = TestClient(create_app())

    first = client.get("/counter")
    second = client.get("/counter")

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json() == {"count": 1}
    assert second.json() == {"count": 2}
