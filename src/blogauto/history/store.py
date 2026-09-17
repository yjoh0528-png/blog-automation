from __future__ import annotations

import json
from datetime import date, datetime, timezone
from pathlib import Path

from ..models import Platform


class HistoryStore:
    """발행 이력을 JSON 파일에 저장한다 (중복 상품 회피 / 일일 게시량 제한용)."""

    def __init__(self, path: str | Path):
        self._path = Path(path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        if not self._path.exists():
            self._path.write_text("[]", encoding="utf-8")

    def _load(self) -> list[dict]:
        return json.loads(self._path.read_text(encoding="utf-8"))

    def _save(self, records: list[dict]) -> None:
        self._path.write_text(
            json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    def record(self, platform: Platform, product_id: str, title: str) -> None:
        records = self._load()
        records.append(
            {
                "platform": platform.value,
                "product_id": product_id,
                "title": title,
                "published_at": datetime.now(timezone.utc).isoformat(),
            }
        )
        self._save(records)

    def recent_product_ids(self, days: int = 30) -> set[str]:
        cutoff = datetime.now(timezone.utc).timestamp() - days * 86400
        ids = set()
        for record in self._load():
            published = datetime.fromisoformat(record["published_at"]).timestamp()
            if published >= cutoff:
                ids.add(record["product_id"])
        return ids

    def count_today(self, platform: Platform) -> int:
        today = date.today().isoformat()
        return sum(
            1
            for record in self._load()
            if record["platform"] == platform.value and record["published_at"].startswith(today)
        )
