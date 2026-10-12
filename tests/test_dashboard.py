from __future__ import annotations

import json
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
        "session_dir": "data/sessions",
        "pending_posts_dir": "data/pending_posts",
        "naver_blog_id": "",
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


def make_ready_project(tmp_path: Path, **overrides) -> Path:
    """dry_run=False + 로그인 세션 + naver_blog_id까지 준비된 프로젝트."""
    project = make_project(tmp_path, dry_run=False, naver_blog_id="myblogid", **overrides)
    session_dir = project / "data" / "sessions"
    session_dir.mkdir(parents=True)
    (session_dir / "naver_blog.json").write_text("{}", encoding="utf-8")
    return project


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


def generate_post(client) -> str:
    resp = client.post("/generate", data={"keyword": "거북목 완화 용품"})
    assert resp.status_code == 302
    return client.get("/posts").get_json()[0]["id"]


def test_index_renders(client):
    resp = client.get("/")
    assert resp.status_code == 200
    assert "블로그 자동화 대시보드".encode() in resp.data


def test_unknown_site_login_status_404(client):
    resp = client.get("/login/unknown_site/status")
    assert resp.status_code == 404


class FakeProcess:
    def __init__(self):
        self._running = True

    def poll(self):
        return None if self._running else 0

    def finish(self):
        self._running = False


def test_start_login_unknown_site_404(client):
    resp = client.post("/login/unknown_site")
    assert resp.status_code == 404


def test_start_login_spawns_process(client, monkeypatch):
    fake = FakeProcess()
    monkeypatch.setattr("dashboard.app.subprocess.Popen", lambda *a, **k: fake)

    resp = client.post("/login/naver_blog")

    assert resp.status_code == 200
    assert resp.get_json()["status"] == "started"


def test_start_login_blocks_duplicate_while_running(client, monkeypatch):
    # 더블클릭/연타로 같은 사이트 로그인 창이 두 개 뜨면 같은 세션 파일을
    # 두고 경쟁하다 TargetClosedError 같은 혼란스러운 실패로 이어진다 -
    # 이미 진행 중이면 새로 띄우지 않고 명확한 메시지로 막아야 한다.
    fake = FakeProcess()
    monkeypatch.setattr("dashboard.app.subprocess.Popen", lambda *a, **k: fake)

    first = client.post("/login/naver_blog")
    assert first.status_code == 200

    second = client.post("/login/naver_blog")
    assert second.status_code == 409
    assert "이미 로그인이 진행 중" in second.get_json()["error"]


def test_start_login_allows_retry_after_process_exits(client, monkeypatch):
    fake = FakeProcess()
    monkeypatch.setattr("dashboard.app.subprocess.Popen", lambda *a, **k: fake)

    first = client.post("/login/naver_blog")
    assert first.status_code == 200

    fake.finish()  # 이전 로그인 프로세스가 끝남(성공/실패/취소 등)

    second = client.post("/login/naver_blog")
    assert second.status_code == 200


def test_generate_with_keyword_and_dry_run_publish(client):
    post_id = generate_post(client)
    posts = client.get("/posts").get_json()
    assert posts[0]["status"] == "pending"
    assert posts[0]["sections"], "구조화된 섹션이 저장되어야 자동화 스크립트가 쓸 수 있다"

    resp = client.post(f"/posts/{post_id}/publish")
    assert resp.status_code == 200
    assert resp.get_json()["status"] == "dry_run"
    assert client.get("/posts").get_json()[0]["status"] == "dry_run"


def test_generate_with_interest_area_collects_no_articles_without_naver_keys(client):
    # NAVER_CLIENT_ID/SECRET이 없으므로 글감 수집은 건너뛰지만, 생성 자체는
    # interest_area를 키워드처럼 사용해 계속 진행돼야 한다.
    resp = client.post("/generate", data={"interest_area": "거북목 완화 용품"})
    assert resp.status_code == 302
    posts = client.get("/posts").get_json()
    assert len(posts) == 1
    assert posts[0]["keyword"] == "거북목 완화 용품"


def test_generate_surfaces_claude_cli_failure_instead_of_blank_500(client, monkeypatch):
    # LLM_BACKEND=claude_print인데 claude 바이너리를 못 찾는 상황(예: Windows에서
    # npm 설치된 claude.cmd를 shell=True 없이 못 찾는 경우)을 흉내낸다. 이전에는
    # ClaudeCliError가 어디서도 잡히지 않아 Flask가 빈 500을 반환했다 - 지금은
    # 원인이 담긴 JSON 에러로 응답해야 한다.
    monkeypatch.setenv("LLM_BACKEND", "claude_print")
    monkeypatch.setattr("blogauto.content.llm.shutil.which", lambda binary: None)

    def fake_run(cmd, **kwargs):
        raise FileNotFoundError("claude not found")

    monkeypatch.setattr("blogauto.content.llm.subprocess.run", fake_run)

    resp = client.post("/generate", data={"keyword": "거북목 완화 용품"})

    assert resp.status_code == 400
    assert "claude -p" in resp.get_json()["error"]
    assert client.get("/posts").get_json() == []


def test_generate_catches_unexpected_exception_with_json_error(client, monkeypatch):
    def boom(*args, **kwargs):
        raise RuntimeError("예상 못한 내부 오류")

    monkeypatch.setattr("dashboard.app.generate_one_post", boom)

    resp = client.post("/generate", data={"keyword": "거북목 완화 용품"})

    assert resp.status_code == 500
    assert "예상 못한 내부 오류" in resp.get_json()["error"]


def test_publish_blocked_by_kill_switch(tmp_path):
    project = make_ready_project(tmp_path, kill_switch=True)
    client = create_app(base_dir=project).test_client()
    post_id = generate_post(client)

    resp = client.post(f"/posts/{post_id}/publish")
    assert resp.status_code == 409
    assert "중단" in resp.get_json()["error"]


def test_publish_requires_naver_session(tmp_path):
    project = make_project(tmp_path, dry_run=False, naver_blog_id="myblogid")
    client = create_app(base_dir=project).test_client()
    post_id = generate_post(client)

    resp = client.post(f"/posts/{post_id}/publish")
    assert resp.status_code == 400
    assert "로그인" in resp.get_json()["error"]


def test_publish_requires_naver_blog_id(tmp_path):
    project = make_project(tmp_path, dry_run=False, naver_blog_id="")
    session_dir = project / "data" / "sessions"
    session_dir.mkdir(parents=True)
    (session_dir / "naver_blog.json").write_text("{}", encoding="utf-8")

    client = create_app(base_dir=project).test_client()
    post_id = generate_post(client)

    resp = client.post(f"/posts/{post_id}/publish")
    assert resp.status_code == 400
    assert "naver_blog_id" in resp.get_json()["error"]


def test_publish_blocked_by_daily_cap(tmp_path):
    project = make_ready_project(tmp_path)

    from blogauto.history.store import HistoryStore
    from blogauto.models import Platform

    HistoryStore(project / "data" / "history.json").record(
        Platform.NAVER_BLOG, "already-posted", "이미 오늘 게시한 글"
    )

    client = create_app(base_dir=project).test_client()
    post_id = generate_post(client)

    resp = client.post(f"/posts/{post_id}/publish")
    assert resp.status_code == 409
    assert "한도" in resp.get_json()["error"]


def test_publish_starts_background_automation_and_writes_post_json(tmp_path):
    project = make_ready_project(tmp_path)
    client = create_app(base_dir=project).test_client()
    post_id = generate_post(client)

    resp = client.post(f"/posts/{post_id}/publish")
    assert resp.status_code == 200
    assert resp.get_json()["status"] == "started"

    # Popen은 논블로킹이므로 실제 자동화 완료를 기다리지 않는다 - 상태가
    # "publishing"으로 바뀌고, 자동화 스크립트가 읽을 post.json이 정확히
    # 쓰였는지만 확인한다 (실제 Playwright 브라우저 구동은 이 환경에서
    # 검증 불가 - README/계획 문서에 명시된 한계).
    assert client.get("/posts").get_json()[0]["status"] == "publishing"

    control_dir = project / "data" / "pending_posts" / f"{post_id}.control"
    payload = json.loads((control_dir / "post.json").read_text(encoding="utf-8"))
    assert payload["title"]
    assert payload["sections"]
    assert "disclosure_text" in payload


def test_publish_status_not_started_before_publish(client):
    post_id = generate_post(client)
    resp = client.get(f"/posts/{post_id}/publish/status")
    assert resp.status_code == 200
    assert resp.get_json()["state"] == "not_started"


def test_publish_status_syncs_published_state_and_records_history(tmp_path):
    project = make_ready_project(tmp_path)
    client = create_app(base_dir=project).test_client()
    post_id = generate_post(client)

    control_dir = project / "data" / "pending_posts" / f"{post_id}.control"
    control_dir.mkdir(parents=True)
    (control_dir / "status.json").write_text(
        json.dumps({"state": "published", "step": "완료", "url": "https://blog.naver.com/x/123"}),
        encoding="utf-8",
    )

    resp = client.get(f"/posts/{post_id}/publish/status")
    assert resp.get_json()["state"] == "published"

    posts = client.get("/posts").get_json()
    assert posts[0]["status"] == "published"

    from blogauto.history.store import HistoryStore
    from blogauto.models import Platform

    history = HistoryStore(project / "data" / "history.json")
    assert history.count_today(Platform.NAVER_BLOG) == 1


def test_publish_status_syncs_failed_state_without_recording_history(tmp_path):
    project = make_ready_project(tmp_path)
    client = create_app(base_dir=project).test_client()
    post_id = generate_post(client)

    control_dir = project / "data" / "pending_posts" / f"{post_id}.control"
    control_dir.mkdir(parents=True)
    (control_dir / "status.json").write_text(
        json.dumps({"state": "failed", "step": "발행 버튼", "message": "못 찾음"}),
        encoding="utf-8",
    )

    client.get(f"/posts/{post_id}/publish/status")
    assert client.get("/posts").get_json()[0]["status"] == "failed"

    from blogauto.history.store import HistoryStore
    from blogauto.models import Platform

    history = HistoryStore(project / "data" / "history.json")
    assert history.count_today(Platform.NAVER_BLOG) == 0


def test_signal_routes_create_signal_files(tmp_path):
    project = make_ready_project(tmp_path)
    client = create_app(base_dir=project).test_client()
    post_id = generate_post(client)

    control_dir = project / "data" / "pending_posts" / f"{post_id}.control"
    control_dir.mkdir(parents=True)

    for action, filename in [
        ("resume", "resume.signal"),
        ("confirm", "confirm.signal"),
        ("cancel", "cancel.signal"),
    ]:
        resp = client.post(f"/posts/{post_id}/publish/{action}")
        assert resp.status_code == 200
        assert (control_dir / filename).exists()


def test_signal_route_404_without_control_dir(client):
    post_id = generate_post(client)
    resp = client.post(f"/posts/{post_id}/publish/resume")
    assert resp.status_code == 404


def test_publish_preview_404_when_missing(client):
    post_id = generate_post(client)
    resp = client.get(f"/posts/{post_id}/publish/preview")
    assert resp.status_code == 404


def test_publish_preview_serves_screenshot(tmp_path):
    project = make_ready_project(tmp_path)
    client = create_app(base_dir=project).test_client()
    post_id = generate_post(client)

    control_dir = project / "data" / "pending_posts" / f"{post_id}.control"
    control_dir.mkdir(parents=True)
    # 최소 유효 PNG 헤더만 있으면 send_file로 서빙되는지 확인 가능
    (control_dir / "preview.png").write_bytes(
        bytes.fromhex("89504e470d0a1a0a0000000d49484452")
    )

    resp = client.get(f"/posts/{post_id}/publish/preview")
    assert resp.status_code == 200
    assert resp.mimetype == "image/png"
