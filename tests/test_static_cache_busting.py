"""The page links /static/app.js, style.css and i18n.js. A browser that cached an old copy kept showing the old UI until a hard refresh.
The server now stamps those three links with a version that changes when any of the files changes, and tells the browser to
re-check the HTML itself each time, so a new release shows up on a normal reload."""

import re
import shutil

import pytest
from starlette.testclient import TestClient

from lab10_fastapi.curriculum_app import main

LINK = re.compile(r'/static/(style\.css|theme-init\.js|i18n\.js|app\.js)\?v=([0-9a-f]{8,})"')


@pytest.fixture()
def client():
    return TestClient(main.app)


def test_the_page_links_the_four_assets_with_one_version(client):
    response = client.get("/")
    assert response.status_code == 200 and "text/html" in response.headers["content-type"]
    found = LINK.findall(response.text)
    assert sorted(name for name, _ in found) == ["app.js", "i18n.js", "style.css", "theme-init.js"]
    assert len({version for _, version in found}) == 1


def test_the_html_itself_is_always_rechecked(client):
    assert "no-cache" in client.get("/").headers["cache-control"]


def test_a_versioned_asset_url_is_still_served(client):
    version = LINK.search(client.get("/").text).group(2)
    for name in ("app.js", "style.css", "i18n.js", "theme-init.js"):
        assert client.get(f"/static/{name}?v={version}").status_code == 200


def test_the_version_changes_when_an_asset_changes(client, monkeypatch, tmp_path):
    copy = tmp_path / "static"
    shutil.copytree(main.STATIC_DIR, copy)
    monkeypatch.setattr(main, "STATIC_DIR", copy)
    before = LINK.search(client.get("/").text).group(2)
    assert LINK.search(client.get("/").text).group(2) == before                    # stable while nothing changes
    (copy / "app.js").write_text((copy / "app.js").read_text(encoding="utf-8") + "\n// changed\n", encoding="utf-8")
    assert LINK.search(client.get("/").text).group(2) != before


def test_the_page_content_is_unchanged_apart_from_the_version(client):
    served = LINK.sub(lambda m: f'/static/{m.group(1)}"', client.get("/").text)
    original = (main.STATIC_DIR / "index.html").read_text(encoding="utf-8")
    assert served.replace("\r\n", "\n") == original.replace("\r\n", "\n")
