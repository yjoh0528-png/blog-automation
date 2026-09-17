from __future__ import annotations

import re

from .llm import LLMClient
from ..disclosure import get_disclosure
from ..models import Keyword, Post, Product, Section
from ..policy import REQUIRED_SECTION_HEADINGS

_SYSTEM_PROMPT = f"""\
너는 실용적인 상품 리뷰 블로그 작성자다. 다음 규칙을 반드시 지켜라.
1. 과장/허위 광고 표현("100% 효과", "무조건", "완치", "최저가 보장" 등)을 쓰지 않는다.
2. 제휴 링크나 대가성 콘텐츠임을 숨기거나 축소하지 않는다.
3. 아래 소제목 구조를 마크다운 "## 제목" 형식으로 반드시, 이 순서대로 포함한다:
   {", ".join(REQUIRED_SECTION_HEADINGS)}
4. 과도한 판매 유도 문구 대신 정보 제공 위주로, 실제 사용 후기처럼 자연스럽게 작성한다.
5. 각 섹션은 2~4문장으로 간결하게 작성한다.
"""


class ContentGenerationError(Exception):
    pass


class ContentGenerator:
    def __init__(self, llm_client: LLMClient):
        self._llm = llm_client

    def generate(self, keyword: Keyword, product: Product, target_audience: str) -> Post:
        title = self._build_title(keyword, product, target_audience)
        user_prompt = (
            f"상품명: {product.title}\n"
            f"타겟 키워드: {keyword.term}\n"
            f"타겟 독자: {target_audience}\n"
            f"카테고리: {product.category or '미지정'}\n\n"
            "위 정보를 바탕으로 마크다운 소제목(##)을 사용한 블로그 본문을 작성해줘."
        )
        raw = self._llm.generate(_SYSTEM_PROMPT, user_prompt)
        sections = self._parse_sections(raw)
        return Post(
            title=title,
            keyword=keyword,
            product=product,
            sections=sections,
            disclosure_text=get_disclosure(product.source),
            tags=[tag for tag in (keyword.term, product.category) if tag],
        )

    @staticmethod
    def _build_title(keyword: Keyword, product: Product, target_audience: str) -> str:
        return f"{product.title} - {target_audience}을 위한 {keyword.term}"

    @staticmethod
    def _parse_sections(raw: str) -> list[Section]:
        sections: list[Section] = []
        current_heading: str | None = None
        current_lines: list[str] = []

        def flush() -> None:
            if current_heading:
                body = "\n".join(current_lines).strip()
                if body:
                    sections.append(Section(heading=current_heading, body=body))

        for line in raw.splitlines():
            match = re.match(r"^#{1,3}\s+(.*)", line)
            if match:
                flush()
                current_heading = match.group(1).strip()
                current_lines = []
            else:
                current_lines.append(line)
        flush()

        if not sections:
            raise ContentGenerationError("LLM 응답에서 소제목 구조를 추출하지 못했습니다.")
        return sections
