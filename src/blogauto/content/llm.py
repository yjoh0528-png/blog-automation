from __future__ import annotations

from abc import ABC, abstractmethod


class LLMClient(ABC):
    @abstractmethod
    def generate(self, system_prompt: str, user_prompt: str) -> str:
        """system/user 프롬프트를 받아 생성된 텍스트를 반환한다."""


class AnthropicLLMClient(LLMClient):
    """Anthropic Claude API 기반 콘텐츠 생성 클라이언트."""

    def __init__(self, api_key: str, model: str = "claude-sonnet-5"):
        import anthropic  # 지연 임포트: 테스트/오프라인 환경에서 의존성 불필요

        self._client = anthropic.Anthropic(api_key=api_key)
        self._model = model

    def generate(self, system_prompt: str, user_prompt: str) -> str:
        response = self._client.messages.create(
            model=self._model,
            max_tokens=2000,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
        )
        return "".join(block.text for block in response.content if block.type == "text")


class TemplateLLMClient(LLMClient):
    """API 키가 없는 테스트/오프라인 환경을 위한 결정론적 폴백."""

    def generate(self, system_prompt: str, user_prompt: str) -> str:
        return (
            "## 핵심 특징\n"
            "이 상품은 실용적인 기능과 무난한 디자인을 갖추고 있어 일상에서 부담 없이 "
            "사용할 수 있습니다.\n\n"
            "## 이런 분께 추천해요\n"
            "관련 고민이 있거나 실용적인 선물을 찾는 분들께 유용한 선택입니다.\n\n"
            "## 사용 팁\n"
            "처음 사용할 때는 제품 설명서를 먼저 확인하고, 본인의 사용 환경에 맞게 "
            "설정을 조절하는 것을 추천합니다.\n\n"
            "## 정리\n"
            "가격 대비 만족도를 중시하는 분들에게 합리적인 선택지 중 하나입니다."
        )
