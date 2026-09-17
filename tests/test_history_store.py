import json
from datetime import datetime, timedelta, timezone

from blogauto.history.store import HistoryStore
from blogauto.models import Platform


def test_record_and_query(tmp_path):
    store = HistoryStore(tmp_path / "history.json")
    assert store.count_today(Platform.GOOGLE_BLOGGER) == 0

    store.record(Platform.GOOGLE_BLOGGER, "p1", "제목1")

    assert store.count_today(Platform.GOOGLE_BLOGGER) == 1
    assert "p1" in store.recent_product_ids(days=30)


def test_recent_product_ids_excludes_old_entries(tmp_path):
    path = tmp_path / "history.json"
    old_date = (datetime.now(timezone.utc) - timedelta(days=40)).isoformat()
    path.write_text(
        json.dumps(
            [
                {
                    "platform": "google_blogger",
                    "product_id": "old",
                    "title": "t",
                    "published_at": old_date,
                }
            ]
        ),
        encoding="utf-8",
    )

    store = HistoryStore(path)

    assert "old" not in store.recent_product_ids(days=30)


def test_count_today_only_counts_matching_platform(tmp_path):
    store = HistoryStore(tmp_path / "history.json")
    store.record(Platform.GOOGLE_BLOGGER, "p1", "제목1")
    store.record(Platform.NAVER_BLOG, "p2", "제목2")

    assert store.count_today(Platform.GOOGLE_BLOGGER) == 1
    assert store.count_today(Platform.TISTORY) == 0
