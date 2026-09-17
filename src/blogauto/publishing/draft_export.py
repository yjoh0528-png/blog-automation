from __future__ import annotations

import logging
import re
from pathlib import Path

from .base import Publisher
from ..models import Post

logger = logging.getLogger(__name__)


class DraftExportPublisher(Publisher):
    """네이버 블로그 / 티스토리처럼 공식 자동 포스팅 API가 없는 플랫폼을 위한 어댑터.

    로그인 자동화(매크로)는 각 플랫폼 이용약관 위반 소지가 있어 구현하지 않는다.
    대신 검수 후 바로 붙여넣기만 하면 되는 초안 파일(Markdown + HTML)을 생성하고,
    사람이 최종 검수 후 직접 게시하도록 안내한다.
    """

    def __init__(self, output_dir: str | Path, platform_label: str):
        self._output_dir = Path(output_dir)
        self._output_dir.mkdir(parents=True, exist_ok=True)
        self._platform_label = platform_label

    def publish(self, post: Post) -> str:
        slug = _slugify(post.title)
        md_path = self._output_dir / f"{slug}.md"
        html_path = self._output_dir / f"{slug}.html"
        md_path.write_text(post.to_markdown(), encoding="utf-8")
        html_path.write_text(post.to_html(), encoding="utf-8")
        logger.info(
            "[%s] 자동 게시 대신 초안을 생성했습니다. 검수 후 직접 게시해주세요: %s",
            self._platform_label,
            md_path,
        )
        return str(md_path)


def _slugify(text: str) -> str:
    slug = re.sub(r"[^0-9a-zA-Z가-힣]+", "-", text).strip("-")
    return slug[:80] or "post"
