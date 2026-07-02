from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from bundesrag.web.app import create_app

FRONTEND_DIST = Path(__file__).resolve().parents[1] / "frontend" / "dist"


def test_create_app_works_without_frontend_build(settings):
    app = create_app(settings=settings)
    client = TestClient(app)

    response = client.get("/api/status")

    assert response.status_code == 200


@pytest.mark.skipif(
    not (FRONTEND_DIST / "index.html").exists(), reason="frontend not built (run npm run build)"
)
def test_serves_frontend_index_when_built(settings):
    app = create_app(settings=settings)
    client = TestClient(app)

    response = client.get("/")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
