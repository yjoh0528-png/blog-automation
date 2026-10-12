from __future__ import annotations

from blogauto.models import Keyword, Post, Product, ProductSource, Section


def make_post(image_url: str | None) -> Post:
    product = Product(
        source=ProductSource.COUPANG_PARTNERS,
        product_id="p1",
        title="목 어깨 안마기",
        original_url="https://example.com/p1",
        affiliate_url="https://example.com/p1?affid=abc",
        image_url=image_url,
    )
    return Post(
        title="목 어깨 안마기 - 직장인을 위한 선물",
        keyword=Keyword(term="거북목 완화 용품"),
        product=product,
        sections=[Section("핵심 특징", "강도 조절이 가능합니다.")],
        disclosure_text="이 포스팅은 쿠팡 파트너스 활동의 일환입니다.",
    )


def test_to_html_embeds_product_image_when_present():
    post = make_post("https://example.com/product.jpg")
    html = post.to_html()
    assert '<img src="https://example.com/product.jpg"' in html
    assert "목 어깨 안마기" in html


def test_to_html_omits_image_tag_when_no_image():
    post = make_post(None)
    assert "<img" not in post.to_html()


def test_to_markdown_embeds_product_image_when_present():
    post = make_post("https://example.com/product.jpg")
    markdown = post.to_markdown()
    assert "![목 어깨 안마기](https://example.com/product.jpg)" in markdown


def test_to_markdown_omits_image_when_no_image():
    post = make_post(None)
    assert "![" not in post.to_markdown()
