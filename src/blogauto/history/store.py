from __future__ import annotations

import json
from datetime import datetime, timezone
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
        # published_at은 UTC로 저장되므로 "오늘"도 UTC 기준으로 비교한다.
        # date.today()(로컬 타임존)와 비교하면 KST(UTC+9) 등에서는 로컬
        # 자정~UTC 자정 사이에 날짜가 어긋나 하루 집계가 샌다.
        today = datetime.now(timezone.utc).date().isoformat()
        return sum(
            1
            for record in self._load()
            if record["platform"] == platform.value and record["published_at"].startswith(today)
        )

    def minutes_since_last_publish(self, platform: Platform) -> float | None:
        """해당 플랫폼의 마지막 발행으로부터 경과한 분(分). 발행 이력이 없으면 None."""
        timestamps = [
            datetime.fromisoformat(record["published_at"])
            for record in self._load()
            if record["platform"] == platform.value
        ]
        if not timestamps:
            return None
        last = max(timestamps)
        return (datetime.now(timezone.utc) - last).total_seconds() / 60
