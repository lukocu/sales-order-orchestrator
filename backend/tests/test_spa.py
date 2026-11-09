from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import create_app

INDEX_HTML = "<!doctype html><title>SPA</title>"


@pytest.fixture
def spa_client(tmp_path: Path) -> Iterator[TestClient]:
    (tmp_path / "index.html").write_text(INDEX_HTML, encoding="utf-8")
    (tmp_path / "assets").mkdir()
    (tmp_path / "assets" / "app.js").write_text("console.log('spa')", encoding="utf-8")
    with TestClient(create_app(static_dir=tmp_path)) as client:
        yield client


@pytest.mark.parametrize("path", ["/", "/dowolna/sciezka"])
def test_non_api_paths_return_index_html(spa_client: TestClient, path: str) -> None:
    response = spa_client.get(path)

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert response.text == INDEX_HTML


def test_existing_static_file_is_served(spa_client: TestClient) -> None:
    response = spa_client.get("/assets/app.js")

    assert response.status_code == 200
    assert response.text == "console.log('spa')"


def test_unknown_api_path_returns_json_404(spa_client: TestClient) -> None:
    response = spa_client.get("/api/nieistnieje")

    assert response.status_code == 404
    assert response.headers["content-type"] == "application/json"
    assert response.json() == {"detail": "Not Found"}


def test_path_traversal_does_not_escape_static_dir(spa_client: TestClient) -> None:
    response = spa_client.get("/..%2F..%2Fetc%2Fpasswd")

    assert response.status_code == 200
    assert response.text == INDEX_HTML


def test_without_static_dir_app_serves_api_only(tmp_path: Path) -> None:
    with TestClient(create_app(static_dir=tmp_path / "missing")) as client:
        assert client.get("/").status_code == 404
