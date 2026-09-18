from __future__ import annotations

from blogauto.research.naver_search import NaverNewsBlogResearch


class FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self._payload


def test_search_news_parses_and_strips_html(monkeypatch):
    captured = {}

    def fake_get(url, params=None, headers=None, timeout=None):
        captured["url"] = url
        captured["params"] = params
        captured["headers"] = headers
        return FakeResponse(
            {
                "items": [
                    {
                        "title": "<b>거북목</b> 완화 용품 인기",
                        "description": "최근 <b>거북목</b> 관련 제품 판매 증가...",
                        "link": "https://news.example.com/1",
                    }
                ]
            }
        )

    monkeypatch.setattr(
        "blogauto.research.naver_search.requests.get", fake_get
    )

    research = NaverNewsBlogResearch("id", "secret")
    results = research.search_news("거북목", display=5)

    assert len(results) == 1
    article = results[0]
    assert article.title == "거북목 완화 용품 인기"
    assert article.description == "최근 거북목 관련 제품 판매 증가..."
    assert article.link == "https://news.example.com/1"
    assert article.source_type == "news"

    assert captured["url"] == "https://openapi.naver.com/v1/search/news.json"
    assert captured["params"]["query"] == "거북목"
    assert captured["params"]["display"] == 5
    assert captured["headers"]["X-Naver-Client-Id"] == "id"
    assert captured["headers"]["X-Naver-Client-Secret"] == "secret"


def test_search_blogs_sets_source_type(monkeypatch):
    def fake_get(url, params=None, headers=None, timeout=None):
        return FakeResponse(
            {
                "items": [
                    {"title": "블로그 글", "description": "요약", "link": "https://blog.example.com/1"}
                ]
            }
        )

    monkeypatch.setattr(
        "blogauto.research.naver_search.requests.get", fake_get
    )

    research = NaverNewsBlogResearch("id", "secret")
    results = research.search_blogs("거북목")

    assert results[0].source_type == "blog"


def test_search_returns_empty_list_when_no_items(monkeypatch):
    def fake_get(url, params=None, headers=None, timeout=None):
        return FakeResponse({"items": []})

    monkeypatch.setattr(
        "blogauto.research.naver_search.requests.get", fake_get
    )

    research = NaverNewsBlogResearch("id", "secret")
    assert research.search_news("없는 검색어") == []
