from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

import yaml


@dataclass
class PlatformConfig:
    enabled: bool = False
    daily_post_cap: int = 1


@dataclass
class Settings:
    seed_keywords: list[str] = field(default_factory=list)
    target_audience_map: dict[str, str] = field(default_factory=dict)
    platforms: dict[str, PlatformConfig] = field(default_factory=dict)
    history_path: str = "data/history.json"
    draft_output_dir: str = "drafts"
    ohouse_csv_path: str = "data/ohouse_products.csv"
    duplicate_lookback_days: int = 30
    # 발행 안전장치: 차단 회피가 아니라 "실수로 인한 실제 게시" 방지가 목적.
    dry_run: bool = True
    kill_switch: bool = False
    min_publish_interval_min: int = 30
    session_dir: str = "data/sessions"
    pending_posts_dir: str = "data/pending_posts"
    # 네이버 블로그 글쓰기 URL 조립용 (예: https://blog.naver.com/<id>?Redirect=Write)
    naver_blog_id: str = ""

    @classmethod
    def load(cls, path: str | Path) -> "Settings":
        raw = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
        platforms = {
            name: PlatformConfig(**cfg) for name, cfg in raw.get("platforms", {}).items()
        }
        return cls(
            seed_keywords=raw.get("seed_keywords", []),
            target_audience_map=raw.get("target_audience_map", {}),
            platforms=platforms,
            history_path=raw.get("history_path", cls.history_path),
            draft_output_dir=raw.get("draft_output_dir", cls.draft_output_dir),
            ohouse_csv_path=raw.get("ohouse_csv_path", cls.ohouse_csv_path),
            duplicate_lookback_days=raw.get(
                "duplicate_lookback_days", cls.duplicate_lookback_days
            ),
            dry_run=raw.get("dry_run", cls.dry_run),
            kill_switch=raw.get("kill_switch", cls.kill_switch),
            min_publish_interval_min=raw.get(
                "min_publish_interval_min", cls.min_publish_interval_min
            ),
            session_dir=raw.get("session_dir", cls.session_dir),
            pending_posts_dir=raw.get("pending_posts_dir", cls.pending_posts_dir),
            naver_blog_id=raw.get("naver_blog_id", cls.naver_blog_id),
        )


def env(name: str, default: str | None = None, required: bool = False) -> str | None:
    value = os.environ.get(name, default)
    if required and not value:
        raise RuntimeError(f"필수 환경변수 누락: {name}")
    return value
