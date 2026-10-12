import pytest

from blogauto.content.generator import ContentGenerationError, ContentGenerator
from blogauto.content.llm import LLMClient, TemplateLLMClient
from blogauto.models import Keyword, Product, ProductSource
from blogauto.research.models import ImageCandidate


def make_product(image_url: str | None = None) -> Product:
    return Product(
        source=ProductSource.COUPANG_PARTNERS,
        product_id="p1",
        title="목 어깨 안마기",
        original_url="https://example.com/p1",
        affiliate_url="https://example.com/p1?affid=abc",
        image_url=image_url,
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


class FakeImageSearch:
    def __init__(self, candidates: list[ImageCandidate]):
        self._candidates = candidates
        self.queries: list[str] = []

    def search(self, query: str, display: int = 4):
        self.queries.append(query)
        return self._candidates


class PickIndexLLMClient(LLMClient):
    """TemplateLLMClient의 본문 생성은 그대로 두고, 이미지 판단만 지정한 인덱스로 고정."""

    def __init__(self, image_choice: str):
        self._template = TemplateLLMClient()
        self.image_calls = 0
        self._image_choice = image_choice

    def generate(self, system_prompt, user_prompt):
        return self._template.generate(system_prompt, user_prompt)

    def generate_with_images(self, system_prompt, user_prompt, image_paths):
        self.image_calls += 1
        return self._image_choice


def test_generate_without_image_search_keeps_official_image_unjudged():
    llm = PickIndexLLMClient("0")
    generator = ContentGenerator(llm)  # image_search 미지정(기본 None)
    keyword = Keyword(term="거북목 완화 용품")

    post = generator.generate(
        keyword, make_product(image_url="https://example.com/official.jpg"), "직장인"
    )

    assert post.product.image_url == "https://example.com/official.jpg"
    assert llm.image_calls == 0  # 후보가 1개뿐이면 AI 판단을 생략한다


def test_generate_with_image_search_lets_ai_pick_among_candidates(monkeypatch):
    def fake_download(url, tmp_dir, index, timeout):
        return tmp_dir / f"candidate_{index}.jpg"

    monkeypatch.setattr("blogauto.content.image_picker._download", fake_download)

    image_search = FakeImageSearch(
        [
            ImageCandidate(url="https://img.example.com/1.jpg", title="후보1"),
            ImageCandidate(url="https://img.example.com/2.jpg", title="후보2"),
        ]
    )
    llm = PickIndexLLMClient("1")  # 공식 이미지(0) 대신 검색 후보 2번째(=전체 인덱스 2)를 고른다
    generator = ContentGenerator(llm, image_search=image_search)
    keyword = Keyword(term="거북목 완화 용품")

    post = generator.generate(
        keyword, make_product(image_url="https://example.com/official.jpg"), "직장인"
    )

    assert image_search.queries == ["목 어깨 안마기 거북목 완화 용품"]
    assert llm.image_calls == 1
    # 후보 순서: [공식 이미지(0), 검색결과1(1), 검색결과2(2)] 중 "1"을 선택
    assert post.product.image_url == "https://img.example.com/1.jpg"


def test_generate_falls_back_when_image_search_fails(monkeypatch):
    class BoomImageSearch:
        def search(self, query, display=4):
            raise RuntimeError("API 장애")

    llm = PickIndexLLMClient("0")
    generator = ContentGenerator(llm, image_search=BoomImageSearch())
    keyword = Keyword(term="거북목 완화 용품")

    post = generator.generate(
        keyword, make_product(image_url="https://example.com/official.jpg"), "직장인"
    )

    assert post.product.image_url == "https://example.com/official.jpg"
    assert llm.image_calls == 0


def test_template_llm_client_generate_with_images_is_deterministic():
    client = TemplateLLMClient()
    assert client.generate_with_images("sys", "user", ["/tmp/a.jpg", "/tmp/b.jpg"]) == "0"
