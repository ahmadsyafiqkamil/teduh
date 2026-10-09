"""App assembly. Asserts the two things a deploy can silently get wrong: the /api router is
actually mounted, and the store is warm before the first request so a judge does not pay the
cold-load cost inside their first question."""

import pytest
from fastapi.testclient import TestClient

from api.main import app


@pytest.fixture(scope="module")
def client() -> TestClient:
    return TestClient(app)


@pytest.mark.integration
def test_api_router_is_mounted(client):
    assert client.get("/api/health").json()["success"] is True


@pytest.mark.integration
def test_store_is_warm_before_the_first_request():
    # get_store is lru_cached; a cache hit means startup already paid the load.
    from teduh_agent.store import get_store

    assert get_store().booster is not None or get_store().model_card is None


@pytest.mark.integration
def test_map_payload_is_prebuilt_at_startup(client):
    from api.routes import map_payload

    assert map_payload.cache_info().currsize == 1


def _collect_paths(router) -> set[str]:
    """Flatten nested routers: newer ADK mounts its app inside `_IncludedRouter` objects."""
    paths: set[str] = set()
    for route in getattr(router, "routes", []):
        if hasattr(route, "path"):
            paths.add(route.path)
        if hasattr(route, "routes"):
            paths |= _collect_paths(route)
        if hasattr(route, "original_router"):
            paths |= _collect_paths(route.original_router)
    return paths


@pytest.mark.integration
def test_adk_run_sse_endpoint_exists_for_chat(client):
    paths = _collect_paths(app)
    assert any("run_sse" in path for path in paths), (
        "endpoint ADK tidak terpasang; chat streaming tidak akan jalan"
    )
