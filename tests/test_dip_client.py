from datetime import date

import httpx
import pytest

from bundesrag.dip.client import DipClient

DRUCKSACHE_RAW = {
    "id": "68852",
    "dokumentnummer": "19/1",
    "datum": "2017-10-24",
    "wahlperiode": 19,
    "drucksachetyp": "Antrag",
    "titel": "Weitergeltung von Geschäftsordnungsrecht",
    "urheber": [{"bezeichnung": "CDU/CSU", "titel": "Fraktion der CDU/CSU", "rolle": "U"}],
    "fundstelle": {
        "id": "68852",
        "dokumentart": "Drucksache",
        "pdf_url": "https://dserver.bundestag.de/btd/19/000/1900001.pdf",
    },
}


def _client(transport: httpx.MockTransport) -> DipClient:
    http_client = httpx.Client(transport=transport)
    return DipClient(api_key="test-key", http_client=http_client)


def test_list_drucksachen_sends_filters_and_auth_header():
    captured_requests = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured_requests.append(request)
        if len(captured_requests) == 1:
            return httpx.Response(
                200,
                json={"numFound": 1, "cursor": "abc", "documents": [DRUCKSACHE_RAW]},
            )
        return httpx.Response(200, json={"numFound": 1, "cursor": "abc", "documents": []})

    client = _client(httpx.MockTransport(handler))
    results = list(
        client.list_drucksachen(
            datum_start=date(2026, 1, 1),
            wahlperiode=21,
            ressort_fdf=["Bundesministerium für Forschung, Technologie und Raumfahrt"],
        )
    )

    assert len(results) == 1
    assert results[0].dokumentnummer == "19/1"
    request = captured_requests[0]
    assert request.headers["authorization"] == "ApiKey test-key"
    assert request.url.params["f.datum.start"] == "2026-01-01"
    assert request.url.params["f.wahlperiode"] == "21"
    assert (
        request.url.params["f.ressort_fdf"]
        == "Bundesministerium für Forschung, Technologie und Raumfahrt"
    )


def test_pagination_follows_cursor_until_results_are_exhausted():
    pages = [
        {"numFound": 2, "cursor": "page2", "documents": [DRUCKSACHE_RAW]},
        {"numFound": 2, "cursor": "page2", "documents": [DRUCKSACHE_RAW]},
        {"numFound": 2, "cursor": "page2", "documents": []},
    ]

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=pages.pop(0))

    client = _client(httpx.MockTransport(handler))
    results = list(client.list_drucksachen())

    assert len(results) == 2


def test_max_results_caps_pagination():
    pages = [
        {
            "numFound": 5,
            "cursor": "page2",
            "documents": [DRUCKSACHE_RAW, DRUCKSACHE_RAW],
        },
        {
            "numFound": 5,
            "cursor": "page3",
            "documents": [DRUCKSACHE_RAW, DRUCKSACHE_RAW],
        },
    ]

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=pages.pop(0))

    client = _client(httpx.MockTransport(handler))
    results = list(client.list_drucksachen(max_results=1))

    assert len(results) == 1


def test_download_pdf_streams_to_disk(tmp_path):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"%PDF-1.4 fake content")

    client = _client(httpx.MockTransport(handler))
    dest = tmp_path / "doc.pdf"

    result = client.download_pdf("https://example.org/doc.pdf", dest)

    assert result == dest
    assert dest.read_bytes() == b"%PDF-1.4 fake content"


def test_download_pdf_interrupted_mid_stream_leaves_no_file_behind(tmp_path):
    def failing_stream():
        yield b"%PDF-1.4 first chunk"
        raise RuntimeError("connection lost")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=failing_stream())

    client = _client(httpx.MockTransport(handler))
    dest = tmp_path / "doc.pdf"

    with pytest.raises(RuntimeError):
        client.download_pdf("https://example.org/doc.pdf", dest)

    # Neither a truncated PDF (which later runs would treat as complete) nor
    # a leftover temp file may remain.
    assert list(tmp_path.iterdir()) == []


def test_download_pdf_skips_existing_file(tmp_path):
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(200, content=b"should not be fetched")

    client = _client(httpx.MockTransport(handler))
    dest = tmp_path / "doc.pdf"
    dest.write_bytes(b"already here")

    client.download_pdf("https://example.org/doc.pdf", dest)

    assert calls == []
    assert dest.read_bytes() == b"already here"
