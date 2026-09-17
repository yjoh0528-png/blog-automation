import pytest

from blogauto.content.generator import ContentGenerationError, ContentGenerator
from blogauto.content.llm import LLMClient, TemplateLLMClient
from blogauto.models import Keyword, Product, ProductSource


def make_product() -> Product:
    return Product(
        source=ProductSource.COUPANG_PARTNERS,
        product_id="p1",
        title="목 어깨 안마기",
        original_url="https://example.com/p1",
        affiliate_url="https://example.com/p1?affid=abc",
    )


def test_generate_produces_expected_sections():
    generator = ContentGenerator(TemplateLLMClient())
    keyword = Keyword(term="거북목 완화 용품")

    post = generator.generate(keyword, make_product(), "장시간 앉아서 일하는 직장인")

    headings = {s.heading for s in post.sections}
    assert {"핵심 특징", "이런 분께 추천해요", "사용 팁", "정리"} <= headings
    assert "장시간 앉아서 일하는 직장인" in post.title
    assert post.disclosure_text


class NoHeadingLLMClient(LLMClient):
    def generate(self, system_prompt: str, user_prompt: str) -> str:
        return "본문에 소제목이 전혀 없습니다."


def test_generate_raises_when_llm_response_has_no_headings():
    generator = ContentGenerator(NoHeadingLLMClient())
    keyword = Keyword(term="거북목 완화 용품")

    with pytest.raises(ContentGenerationError):
        generator.generate(keyword, make_product(), "직장인")
