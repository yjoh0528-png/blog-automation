from __future__ import annotations

from blogauto.research.naver_image_search import NaverImageSearch


class FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self._payload


def test_search_parses_items_and_strips_html(monkeypatch):
    captured = {}

    def fake_get(url, params=None, headers=None, timeout=None):
        captured["url"] = url
        captured["params"] = params
        captured["headers"] = headers
        return FakeResponse(
            {
                "items": [
                    {
                        "title": "<b>거북목</b> 쿠션 사진",
                        "link": "https://img.example.com/1.jpg",
                        "sizewidth": "640",
                        "sizeheight": "480",
                    }
                ]
            }
        )

    monkeypatch.setattr("blogauto.research.naver_image_search.requests.get", fake_get)

    search = NaverImageSearch("id", "secret")
    results = search.search("거북목 쿠션", display=4)

    assert len(results) == 1
    candidate = results[0]
    assert candidate.url == "https://img.example.com/1.jpg"
    assert candidate.title == "거북목 쿠션 사진"
    assert candidate.width == 640
    assert candidate.height == 480

    assert captured["url"] == "https://openapi.naver.com/v1/search/image"
    assert captured["params"]["query"] == "거북목 쿠션"
    assert captured["params"]["display"] == 4
    assert captured["headers"]["X-Naver-Client-Id"] == "id"
    assert captured["headers"]["X-Naver-Client-Secret"] == "secret"


def test_search_skips_items_without_link(monkeypatch):
    def fake_get(url, params=None, headers=None, timeout=None):
        return FakeResponse({"items": [{"title": "링크 없음"}]})

    monkeypatch.setattr("blogauto.research.naver_image_search.requests.get", fake_get)

    search = NaverImageSearch("id", "secret")
    assert search.search("아무거나") == []


def test_search_returns_empty_list_when_no_items(monkeypatch):
    def fake_get(url, params=None, headers=None, timeout=None):
        return FakeResponse({"items": []})

    monkeypatch.setattr("blogauto.research.naver_image_search.requests.get", fake_get)

    search = NaverImageSearch("id", "secret")
    assert search.search("없는 검색어") == []
