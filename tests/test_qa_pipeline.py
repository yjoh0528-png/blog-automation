import pytest

from blogauto.content.generator import ContentGenerator
from blogauto.content.llm import LLMClient
from blogauto.models import Keyword, Product, ProductSource
from blogauto.qa.pipeline import QAFailedError, generate_with_verification


def make_product() -> Product:
    return Product(
        source=ProductSource.COUPANG_PARTNERS,
        product_id="p1",
        title="목 어깨 안마기",
        original_url="https://example.com/p1",
    )


class BannedPhraseLLMClient(LLMClient):
    def generate(self, system_prompt: str, user_prompt: str) -> str:
        return (
            "## 핵심 특징\n100% 효과가 보장되는 제품입니다.\n\n"
            "## 이런 분께 추천해요\n직장인에게 추천합니다.\n\n"
            "## 사용 팁\n취침 전 사용하세요.\n\n"
            "## 정리\n좋은 선택입니다."
        )


def test_generate_with_verification_raises_after_max_attempts():
    generator = ContentGenerator(BannedPhraseLLMClient())

    with pytest.raises(QAFailedError):
        generate_with_verification(
            generator,
            Keyword(term="거북목 완화 용품"),
            make_product(),
            "직장인",
            recent_product_ids=set(),
            max_attempts=2,
        )


class ValidLLMClient(LLMClient):
    def generate(self, system_prompt: str, user_prompt: str) -> str:
        return (
            "## 핵심 특징\n강도 조절이 가능해 사용감이 좋습니다.\n\n"
            "## 이런 분께 추천해요\n장시간 앉아서 일하는 직장인에게 추천합니다.\n\n"
            "## 사용 팁\n취침 전 15분 정도 사용하는 것을 추천합니다.\n\n"
            "## 정리\n가격 대비 만족스러운 선택지입니다."
        )


def test_generate_with_verification_succeeds_on_valid_content():
    generator = ContentGenerator(ValidLLMClient())

    post = generate_with_verification(
        generator,
        Keyword(term="거북목 완화 용품"),
        make_product(),
        "직장인",
        recent_product_ids=set(),
    )

    assert post.title
