from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from dashboard.app import create_app


def make_project(tmp_path: Path, **settings_overrides) -> Path:
    (tmp_path / "config").mkdir()
    (tmp_path / "data").mkdir()

    ohouse_csv = tmp_path / "data" / "ohouse_products.csv"
    ohouse_csv.write_text(
        "product_id,title,url,affiliate_url,price,image_url,category\n"
        "oh-1,거북목 완화 용품 목쿠션,https://ohou.se/a,https://ohou.se/a?affid=test,29900,,홈리빙\n",
        encoding="utf-8",
    )

    settings = {
        "seed_keywords": ["거북목 완화 용품"],
        "target_audience_map": {"거북목 완화 용품": "직장인"},
        "platforms": {"naver_blog": {"enabled": True, "daily_post_cap": 1}},
        "history_path": "data/history.json",
        "draft_output_dir": "drafts",
        "ohouse_csv_path": str(ohouse_csv),
        "duplicate_lookback_days": 30,
        "dry_run": True,
        "kill_switch": False,
        "min_publish_interval_min": 30,
        "naver_post_script_path": "scripts/recorded/naver_post.py",
        "session_dir": "data/sessions",
        "pending_posts_dir": "data/pending_posts",
    }
    settings.update(settings_overrides)
    (tmp_path / "config" / "settings.yaml").write_text(
        yaml.safe_dump(settings, allow_unicode=True), encoding="utf-8"
    )

    sites = {
        "sites": {
            "naver_blog": {"label": "네이버 블로그", "login_url": "https://example.com/login"},
        }
    }
    (tmp_path / "config" / "sites.yaml").write_text(
        yaml.safe_dump(sites, allow_unicode=True), encoding="utf-8"
    )

    return tmp_path


@pytest.fixture(autouse=True)
def _clear_provider_env(monkeypatch):
    for name in (
        "NAVER_CLIENT_ID",
        "NAVER_CLIENT_SECRET",
        "COUPANG_ACCESS_KEY",
        "COUPANG_SECRET_KEY",
        "ANTHROPIC_API_KEY",
    ):
        monkeypatch.delenv(name, raising=False)
    # 기본 LLM_BACKEND는 claude_print(실제 claude -p CLI 호출)이므로,
    # 테스트에서는 결정론적 템플릿 폴백을 강제해 외부 프로세스 호출을 막는다.
    monkeypatch.setenv("LLM_BACKEND", "template")


@pytest.fixture
def client(tmp_path):
    project = make_project(tmp_path)
    app = create_app(base_dir=project)
    return app.test_client()


def test_index_renders(client):
    resp = client.get("/")
    assert resp.status_code == 200
    assert "블로그 자동화 대시보드".encode() in resp.data


def test_unknown_site_login_status_404(client):
    resp = client.get("/login/unknown_site/status")
    assert resp.status_code == 404


def test_generate_and_dry_run_publish(client):
    resp = client.post("/generate", data={"keyword": "거북목 완화 용품"})
    assert resp.status_code == 302

    posts = client.get("/posts").get_json()
    assert len(posts) == 1
    assert posts[0]["status"] == "pending"
    post_id = posts[0]["id"]

    resp = client.post(f"/posts/{post_id}/publish")
    assert resp.status_code == 200
    assert resp.get_json()["status"] == "dry_run"

    posts = client.get("/posts").get_json()
    assert posts[0]["status"] == "dry_run"


def test_publish_blocked_by_kill_switch(tmp_path):
    project = make_project(tmp_path, dry_run=False, kill_switch=True)
    client = create_app(base_dir=project).test_client()

    client.post("/generate", data={"keyword": "거북목 완화 용품"})
    post_id = client.get("/posts").get_json()[0]["id"]

    resp = client.post(f"/posts/{post_id}/publish")
    assert resp.status_code == 409
    assert "중단" in resp.get_json()["error"]


def test_publish_requires_recorded_script(tmp_path):
    project = make_project(tmp_path, dry_run=False)
    client = create_app(base_dir=project).test_client()

    client.post("/generate", data={"keyword": "거북목 완화 용품"})
    post_id = client.get("/posts").get_json()[0]["id"]

    resp = client.post(f"/posts/{post_id}/publish")
    assert resp.status_code == 400
    assert "스크립트" in resp.get_json()["error"]


def test_publish_requires_naver_session(tmp_path):
    project = make_project(tmp_path, dry_run=False)
    script_dir = project / "scripts" / "recorded"
    script_dir.mkdir(parents=True)
    (script_dir / "naver_post.py").write_text("import sys\nsys.exit(0)\n", encoding="utf-8")

    client = create_app(base_dir=project).test_client()
    client.post("/generate", data={"keyword": "거북목 완화 용품"})
    post_id = client.get("/posts").get_json()[0]["id"]

    resp = client.post(f"/posts/{post_id}/publish")
    assert resp.status_code == 400
    assert "로그인" in resp.get_json()["error"]


def test_publish_success_with_recorded_script(tmp_path):
    project = make_project(tmp_path, dry_run=False)

    session_dir = project / "data" / "sessions"
    session_dir.mkdir(parents=True)
    (session_dir / "naver_blog.json").write_text("{}", encoding="utf-8")

    script_dir = project / "scripts" / "recorded"
    script_dir.mkdir(parents=True)
    (script_dir / "naver_post.py").write_text("import sys\nsys.exit(0)\n", encoding="utf-8")

    client = create_app(base_dir=project).test_client()
    client.post("/generate", data={"keyword": "거북목 완화 용품"})
    post_id = client.get("/posts").get_json()[0]["id"]

    resp = client.post(f"/posts/{post_id}/publish")
    assert resp.status_code == 200
    assert resp.get_json()["status"] == "published"
    assert client.get("/posts").get_json()[0]["status"] == "published"


def test_publish_reports_failure_from_recorded_script(tmp_path):
    project = make_project(tmp_path, dry_run=False)

    session_dir = project / "data" / "sessions"
    session_dir.mkdir(parents=True)
    (session_dir / "naver_blog.json").write_text("{}", encoding="utf-8")

    script_dir = project / "scripts" / "recorded"
    script_dir.mkdir(parents=True)
    (script_dir / "naver_post.py").write_text(
        "import sys\nprint('boom', file=sys.stderr)\nsys.exit(1)\n", encoding="utf-8"
    )

    client = create_app(base_dir=project).test_client()
    client.post("/generate", data={"keyword": "거북목 완화 용품"})
    post_id = client.get("/posts").get_json()[0]["id"]

    resp = client.post(f"/posts/{post_id}/publish")
    assert resp.status_code == 500
    assert client.get("/posts").get_json()[0]["status"] == "failed"


def test_publish_blocked_by_daily_cap(tmp_path):
    project = make_project(tmp_path, dry_run=False)

    session_dir = project / "data" / "sessions"
    session_dir.mkdir(parents=True)
    (session_dir / "naver_blog.json").write_text("{}", encoding="utf-8")

    script_dir = project / "scripts" / "recorded"
    script_dir.mkdir(parents=True)
    (script_dir / "naver_post.py").write_text("import sys\nsys.exit(0)\n", encoding="utf-8")

    from blogauto.history.store import HistoryStore
    from blogauto.models import Platform

    history = HistoryStore(project / "data" / "history.json")
    history.record(Platform.NAVER_BLOG, "already-posted", "이미 오늘 게시한 글")

    client = create_app(base_dir=project).test_client()
    client.post("/generate", data={"keyword": "거북목 완화 용품"})
    post_id = client.get("/posts").get_json()[0]["id"]

    resp = client.post(f"/posts/{post_id}/publish")
    assert resp.status_code == 409
    assert "한도" in resp.get_json()["error"]
