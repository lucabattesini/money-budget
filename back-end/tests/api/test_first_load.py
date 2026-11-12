"""What makes the first visit fast: answers are compressed and the built files can be kept by the browser."""

from api.app import LONG_CACHE, cache_control_for


def test_big_answers_are_compressed_for_browsers_that_accept_it(client):
    response = client.get("/openapi.json", headers={"Accept-Encoding": "gzip"})

    assert response.status_code == 200
    assert response.headers["content-encoding"] == "gzip"
    assert response.json()["openapi"]  # and it still reads back as the same document


def test_nothing_is_compressed_for_a_client_that_does_not_ask(client):
    response = client.get("/openapi.json", headers={"Accept-Encoding": "identity"})

    assert "content-encoding" not in response.headers


def test_built_files_are_kept_for_a_year_but_the_page_and_the_api_are_not():
    assert cache_control_for("/assets/index-B5oJ62Zb.js") == LONG_CACHE
    assert "immutable" in LONG_CACHE
    for path in ("/", "/index.html", "/sw.js", "/manifest.json", "/transactions/", "/budgets"):
        assert cache_control_for(path) is None
