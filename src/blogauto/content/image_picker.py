from __future__ import annotations

import logging
import re
import tempfile
from pathlib import Path

import requests

from .llm import LLMClient
from ..research.models import ImageCandidate

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = (
    "너는 블로그 글에 쓸 대표 이미지를 고르는 편집자다. 주어진 이미지들을 "
    "번호 순서대로 직접 본 뒤, 글 주제와 가장 잘 어울리고 실제 상품/대상이 "
    "선명하게 나온 사진의 번호를 숫자 하나로만 답하라. 적합한 사진이 "
    "하나도 없으면 'NONE'이라고만 답하라. 번호나 NONE 외의 다른 설명은 "
    "쓰지 마라."
)

_MAX_CANDIDATES = 5
_MAX_BYTES = 8 * 1024 * 1024


def pick_best_image(
    llm_client: LLMClient,
    candidates: list[ImageCandidate],
    context: str,
    timeout: float = 10.0,
) -> ImageCandidate | None:
    """여러 이미지 후보 중 AI가 글 맥락에 가장 어울리는 것을 고른다.

    후보를 로컬로 내려받아 LLM에게 직접 보여주고 판단하게 한다. 다운로드나
    판단 중 어느 단계가 실패해도 조용히 (다운로드에 성공한) 첫 번째 후보로
    폴백한다 - 이미지 선택 실패로 전체 글 생성 파이프라인이 막히면 안 된다.
    """
    usable = candidates[:_MAX_CANDIDATES]
    if not usable:
        return None

    with tempfile.TemporaryDirectory(prefix="blogauto_img_") as tmp:
        downloaded: list[tuple[ImageCandidate, Path]] = []
        for i, candidate in enumerate(usable):
            path = _download(candidate.url, Path(tmp), i, timeout)
            if path is not None:
                downloaded.append((candidate, path))

        if not downloaded:
            logger.warning("이미지 후보를 하나도 내려받지 못했습니다.")
            return None
        if len(downloaded) == 1:
            return downloaded[0][0]

        prompt = f"글 주제: {context}\n\n" + "\n".join(
            f"{i}번: {path}" for i, (_, path) in enumerate(downloaded)
        )
        try:
            raw = llm_client.generate_with_images(
                _SYSTEM_PROMPT, prompt, [str(path) for _, path in downloaded]
            ).strip()
        except Exception as exc:  # noqa: BLE001 - 백엔드별 예외 타입이 달라 폭넓게 받는다
            logger.warning("이미지 판단 중 오류 발생, 첫 번째 후보로 대체합니다: %s", exc)
            return downloaded[0][0]

        return _parse_choice(raw, downloaded)


def _parse_choice(
    raw: str, downloaded: list[tuple[ImageCandidate, Path]]
) -> ImageCandidate | None:
    match = re.search(r"\d+", raw)
    if not match:
        if "NONE" in raw.upper():
            return None
        return downloaded[0][0]
    index = int(match.group())
    if index >= len(downloaded):
        index = 0
    return downloaded[index][0]


def _download(url: str, tmp_dir: Path, index: int, timeout: float) -> Path | None:
    try:
        response = requests.get(url, timeout=timeout, stream=True)
        response.raise_for_status()
        content_type = response.headers.get("content-type", "")
        if not content_type.startswith("image/"):
            return None
        ext = content_type.split("/")[-1].split(";")[0].strip() or "jpg"
        out_path = tmp_dir / f"candidate_{index}.{ext}"
        size = 0
        with out_path.open("wb") as f:
            for chunk in response.iter_content(chunk_size=65536):
                size += len(chunk)
                if size > _MAX_BYTES:
                    out_path.unlink(missing_ok=True)
                    return None
                f.write(chunk)
        return out_path
    except requests.RequestException as exc:
        logger.warning("이미지 후보 다운로드 실패 (%s): %s", url, exc)
        return None
