from __future__ import annotations

import json
import mimetypes
import subprocess
from abc import ABC, abstractmethod


class LLMClient(ABC):
    @abstractmethod
    def generate(self, system_prompt: str, user_prompt: str) -> str:
        """system/user 프롬프트를 받아 생성된 텍스트를 반환한다."""

    def generate_with_images(
        self, system_prompt: str, user_prompt: str, image_paths: list[str]
    ) -> str:
        """이미지를 함께 보여주고 응답을 받는다 (예: 여러 후보 중 적합한 사진 고르기).

        기본 구현은 비전 입력을 지원하지 않는 백엔드를 위한 폴백으로,
        이미지를 무시하고 텍스트만으로 응답한다. 실제 이미지를 보고
        판단해야 하는 백엔드(claude -p, Anthropic API)는 이 메서드를
        오버라이드한다.
        """
        return self.generate(system_prompt, user_prompt)


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

    def generate_with_images(
        self, system_prompt: str, user_prompt: str, image_paths: list[str]
    ) -> str:
        import base64

        content: list[dict] = [{"type": "text", "text": user_prompt}]
        for path in image_paths:
            with open(path, "rb") as f:
                data = base64.standard_b64encode(f.read()).decode("utf-8")
            content.append(
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": _guess_image_media_type(path),
                        "data": data,
                    },
                }
            )
        response = self._client.messages.create(
            model=self._model,
            max_tokens=500,
            system=system_prompt,
            messages=[{"role": "user", "content": content}],
        )
        return "".join(block.text for block in response.content if block.type == "text")


def _guess_image_media_type(path: str) -> str:
    guessed, _ = mimetypes.guess_type(path)
    if guessed in ("image/jpeg", "image/png", "image/gif", "image/webp"):
        return guessed
    return "image/jpeg"


class ClaudeCliError(Exception):
    pass


class ClaudePrintModeLLMClient(LLMClient):
    """Claude Code CLI(`claude -p`, 헤드리스 출력 모드) 기반 콘텐츠 생성 클라이언트.

    로컬에 로그인된 Claude 구독(Pro/Max) 세션의 인증을 그대로 사용하므로
    ANTHROPIC_API_KEY 과금 없이 콘텐츠를 생성한다. Anthropic 정책상 구독
    OAuth는 무인 클라우드 자동화 용도가 아니므로, 반드시 사용자가 로컬에서
    직접 실행하는 경로에서만 사용할 것.
    """

    def __init__(
        self,
        model: str = "sonnet",
        timeout: float = 180.0,
        binary: str = "claude",
    ):
        self._model = model
        self._timeout = timeout
        self._binary = binary

    def generate(self, system_prompt: str, user_prompt: str) -> str:
        try:
            result = subprocess.run(
                [
                    self._binary,
                    "-p",
                    user_prompt,
                    "--system-prompt",
                    system_prompt,
                    "--output-format",
                    "json",
                    "--model",
                    self._model,
                ],
                capture_output=True,
                text=True,
                timeout=self._timeout,
            )
        except FileNotFoundError as exc:
            raise ClaudeCliError(
                f"'{self._binary}' 실행 파일을 찾을 수 없습니다. Claude Code CLI가 "
                "설치되어 있고 로그인되어 있는지 확인하세요."
            ) from exc
        except subprocess.TimeoutExpired as exc:
            raise ClaudeCliError(f"claude CLI 응답이 {self._timeout}초 내에 오지 않았습니다.") from exc

        if result.returncode != 0:
            raise ClaudeCliError(
                f"claude CLI 실행 실패 (exit {result.returncode}): {result.stderr.strip()}"
            )
        try:
            payload = json.loads(result.stdout)
        except json.JSONDecodeError as exc:
            raise ClaudeCliError(
                f"claude CLI 응답 JSON 파싱 실패: {result.stdout[:500]!r}"
            ) from exc
        if payload.get("is_error"):
            raise ClaudeCliError(f"claude CLI가 오류를 반환했습니다: {payload.get('result')}")
        return payload.get("result", "")

    def generate_with_images(
        self, system_prompt: str, user_prompt: str, image_paths: list[str]
    ) -> str:
        # claude -p는 프롬프트에 로컬 파일 경로가 언급되면 자체 Read 툴로
        # 그 파일(이미지 포함)을 직접 읽어 응답에 반영한다 - 별도의 비전
        # API 호출 코드 없이 같은 subprocess 경로를 재사용할 수 있다.
        paths_block = "\n".join(f"- {path}" for path in image_paths)
        full_prompt = (
            f"{user_prompt}\n\n"
            "아래 로컬 이미지 파일들을 각각 Read 도구로 직접 열어서 확인한 뒤 답하라:\n"
            f"{paths_block}"
        )
        return self.generate(system_prompt, full_prompt)


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

    def generate_with_images(
        self, system_prompt: str, user_prompt: str, image_paths: list[str]
    ) -> str:
        # 오프라인/테스트용: 항상 첫 번째 후보를 결정론적으로 선택한다.
        return "0"
