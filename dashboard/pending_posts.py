from __future__ import annotations

import json
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from blogauto.models import Post


@dataclass
class PendingPost:
    id: str
    title: str
    markdown: str
    html: str
    platform: str
    product_id: str
    product_title: str
    keyword: str
    created_at: str
    status: str = "pending"  # pending | dry_run | published | failed | canceled
    # 자동 편집기(scripts/naver_auto_publish.py)가 쓰는 구조화된 데이터.
    sections: list[dict] = field(default_factory=list)
    image_url: str | None = None
    disclosure_text: str = ""
    product_link: str = ""

    def for_automation(self) -> dict:
        """scripts/naver_auto_publish.py에 넘길 JSON 페이로드."""
        return {
            "title": self.title,
            "sections": self.sections,
            "image_url": self.image_url,
            "product_link": self.product_link,
            "disclosure_text": self.disclosure_text,
        }


class PendingPostStore:
    """생성된 초안을 로컬 JSON 파일로 관리한다 (대시보드용)."""

    def __init__(self, directory: str | Path):
        self._dir = Path(directory)
        self._dir.mkdir(parents=True, exist_ok=True)

    def save(self, post: Post, platform: str) -> PendingPost:
        pending = PendingPost(
            id=uuid.uuid4().hex[:12],
            title=post.title,
            markdown=post.to_markdown(),
            html=post.to_html(),
            platform=platform,
            product_id=post.product.product_id,
            product_title=post.product.title,
            keyword=post.keyword.term,
            created_at=datetime.now(timezone.utc).isoformat(),
            sections=[{"heading": s.heading, "body": s.body} for s in post.sections],
            image_url=post.product.image_url,
            disclosure_text=post.disclosure_text,
            product_link=post.product.link,
        )
        self._write(pending)
        return pending

    def get(self, post_id: str) -> PendingPost | None:
        path = self._path(post_id)
        if not path.exists():
            return None
        return PendingPost(**json.loads(path.read_text(encoding="utf-8")))

    def list_all(self) -> list[PendingPost]:
        paths = sorted(self._dir.glob("*.json"), reverse=True)
        return [PendingPost(**json.loads(p.read_text(encoding="utf-8"))) for p in paths]

    def update_status(self, post_id: str, status: str) -> None:
        pending = self.get(post_id)
        if pending is None:
            raise KeyError(f"초안을 찾을 수 없습니다: {post_id}")
        pending.status = status
        self._write(pending)

    def _write(self, pending: PendingPost) -> None:
        self._path(pending.id).write_text(
            json.dumps(asdict(pending), ensure_ascii=False, indent=2), encoding="utf-8"
        )

    def _path(self, post_id: str) -> Path:
        return self._dir / f"{post_id}.json"
