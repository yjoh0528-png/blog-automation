from blogauto.models import ProductSource
from blogauto.product_sources.ohouse_curator import OhouseCuratorCsvSource


def test_ohouse_csv_source_filters_by_keyword(tmp_path):
    csv_path = tmp_path / "products.csv"
    csv_path.write_text(
        "product_id,title,url,affiliate_url,price,image_url,category\n"
        "oh-1,거북목 방지 목쿠션,https://ohou.se/a,https://ohou.se/a?affid=x,29900,,홈리빙\n"
        "oh-2,욕실 매트,https://ohou.se/b,https://ohou.se/b?affid=x,15900,,홈리빙\n",
        encoding="utf-8",
    )
    source = OhouseCuratorCsvSource(csv_path)

    results = source.search("목쿠션")

    assert len(results) == 1
    product = results[0]
    assert product.source == ProductSource.OHOUSE_CURATOR
    assert product.title == "거북목 방지 목쿠션"
    assert product.link == "https://ohou.se/a?affid=x"


def test_ohouse_csv_source_returns_empty_when_file_missing(tmp_path):
    source = OhouseCuratorCsvSource(tmp_path / "missing.csv")

    assert source.search("아무거나") == []


def test_naver_shopping_affiliate_link_template(monkeypatch):
    from blogauto.product_sources.naver_shopping import NaverShoppingSource

    class FakeResponse:
        def raise_for_status(self):
            pass

        def json(self):
            return {
                "items": [
                    {
                        "productId": "n1",
                        "title": "<b>목</b>쿠션",
                        "link": "https://shopping.naver.com/p1",
                        "lprice": "19900",
                        "image": "https://example.com/i.jpg",
                        "category1": "생활용품",
                    }
                ]
            }

    def fake_get(url, params=None, headers=None, timeout=None):
        return FakeResponse()

    monkeypatch.setattr(
        "blogauto.product_sources.naver_shopping.requests.get", fake_get
    )

    source = NaverShoppingSource(
        "id", "secret", affiliate_link_template="https://aff.example.com/go?url={url}"
    )
    results = source.search("목쿠션")

    assert len(results) == 1
    product = results[0]
    assert product.title == "목쿠션"
    assert product.link == "https://aff.example.com/go?url=https://shopping.naver.com/p1"
