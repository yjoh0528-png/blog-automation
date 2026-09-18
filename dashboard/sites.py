from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml


@dataclass
class Site:
    key: str
    label: str
    login_url: str


def load_sites(path: str | Path = "config/sites.yaml") -> dict[str, Site]:
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    return {
        key: Site(key=key, label=cfg["label"], login_url=cfg["login_url"])
        for key, cfg in raw.get("sites", {}).items()
    }
