"""Lab 11 — การเสิร์ฟไฟล์ static: บีบอัด gzip และ Cache-Control ตามชนิดไฟล์.

ลิงก์ที่มี ?v=<hash> เปลี่ยนตามเนื้อหา จึงแคชได้ยาวและเปลี่ยนไฟล์แล้วเบราว์เซอร์ไม่ค้างของเก่า
(หน้า / ยัง no-cache เสมอ: ดู test_static_cache_busting.py)
"""

import pytest
from starlette.testclient import TestClient

from lab10_fastapi.curriculum_app import main


@pytest.fixture(scope="module")
def client():
    return TestClient(main.app)


def get(client, url, gzip=True):
    return client.get(url, headers={"Accept-Encoding": "gzip" if gzip else "identity"})


@pytest.mark.parametrize("name", ["app.js", "style.css", "i18n.js"])
def test_text_assets_are_compressed_and_much_smaller(client, name):
    version = main.asset_version()
    packed = get(client, f"/static/{name}?v={version}")
    plain = get(client, f"/static/{name}?v={version}", gzip=False)
    assert packed.status_code == plain.status_code == 200
    assert packed.headers.get("content-encoding") == "gzip" and "content-encoding" not in plain.headers
    assert packed.content == plain.content                              # คลายแล้วเนื้อหาเท่าเดิม
    assert packed.num_bytes_downloaded < plain.num_bytes_downloaded * 0.5


def test_fonts_are_not_compressed_again(client):
    response = get(client, "/static/fonts/noto-sans-thai-thai-400-normal.woff2")
    assert response.status_code == 200 and "content-encoding" not in response.headers


def test_versioned_assets_are_cached_for_a_year_and_marked_immutable(client):
    version = main.asset_version()
    for name in ("app.js", "style.css", "i18n.js"):
        control = get(client, f"/static/{name}?v={version}").headers["cache-control"]
        assert "max-age=31536000" in control and "immutable" in control and "public" in control


def test_the_same_asset_without_a_version_is_always_revalidated(client):
    assert get(client, "/static/app.js").headers["cache-control"] == "no-cache"


def test_fonts_are_cached_for_a_week_not_forever(client):
    control = get(client, "/static/fonts/noto-sans-thai-thai-400-normal.woff2").headers["cache-control"]
    assert control == "public, max-age=604800" and "immutable" not in control


def test_the_html_page_is_still_rechecked_every_time(client):
    assert get(client, "/").headers["cache-control"] == "no-cache"


def test_missing_static_files_are_not_given_long_cache_headers(client):
    response = get(client, "/static/does-not-exist.js?v=abc")
    assert response.status_code == 404 and "cache-control" not in response.headers


def test_the_page_links_point_at_the_url_that_gets_the_long_cache(client):
    html = get(client, "/").text
    version = main.asset_version()
    for name in ("style.css", "i18n.js", "app.js"):
        assert f"/static/{name}?v={version}" in html


def test_api_responses_keep_working_through_the_compression_layer(client):
    response = get(client, "/api/health")
    assert response.status_code == 200 and response.json()
