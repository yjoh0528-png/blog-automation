import json
import time
from datetime import datetime, timedelta, timezone

import pytest

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


def test_minutes_since_last_publish(tmp_path):
    store = HistoryStore(tmp_path / "history.json")
    assert store.minutes_since_last_publish(Platform.NAVER_BLOG) is None

    store.record(Platform.NAVER_BLOG, "p1", "제목1")
    elapsed = store.minutes_since_last_publish(Platform.NAVER_BLOG)
    assert elapsed is not None
    assert 0 <= elapsed < 1
    assert store.minutes_since_last_publish(Platform.TISTORY) is None


@pytest.mark.skipif(not hasattr(time, "tzset"), reason="tzset은 유닉스 계열에서만 지원됨")
def test_count_today_is_timezone_independent(tmp_path, monkeypatch):
    # published_at은 UTC로 저장되므로, count_today도 로컬 타임존과 무관하게
    # 같은 결과를 내야 한다. 로컬 타임존을 UTC와 크게 다른 값으로 바꿔도
    # 방금 기록한 건이 "오늘"에서 누락되면 안 된다.
    monkeypatch.setenv("TZ", "Etc/GMT+12")  # UTC-12
    time.tzset()
    try:
        store = HistoryStore(tmp_path / "history.json")
        store.record(Platform.GOOGLE_BLOGGER, "p1", "제목1")
        assert store.count_today(Platform.GOOGLE_BLOGGER) == 1
    finally:
        monkeypatch.delenv("TZ", raising=False)
        time.tzset()
