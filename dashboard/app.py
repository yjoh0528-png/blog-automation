from __future__ import annotations

import json
import logging
import subprocess
import sys
from pathlib import Path

from flask import Flask, jsonify, redirect, render_template, request, send_file, url_for

from blogauto.config import Settings
from blogauto.history.store import HistoryStore
from blogauto.models import Platform

from .generate import NoContentGeneratedError, generate_one_post
from .pending_posts import PendingPost, PendingPostStore
from .playwright_setup import ensure_playwright_ready, is_playwright_installed
from .sites import Site, load_sites

logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parent.parent


def create_app(
    base_dir: Path | None = None,
    settings_path: Path | None = None,
    sites_path: Path | None = None,
) -> Flask:
    """대시보드 Flask 앱을 만든다.

    base_dir/settings_path/sites_path는 테스트에서 실제 저장소 대신
    임시 디렉터리를 가리키게 하기 위한 주입 지점이다. 운영 시에는 모두
    저장소 루트 기준 기본값을 쓴다.
    """
    base_dir = base_dir or REPO_ROOT
    settings_path = settings_path or (base_dir / "config" / "settings.yaml")
    sites_path = sites_path or (base_dir / "config" / "sites.yaml")

    app = Flask(__name__)
    active_logins: dict[str, subprocess.Popen] = {}

    def load_settings() -> Settings:
        return Settings.load(settings_path)

    def resolve(relative: str) -> Path:
        return base_dir / relative

    def session_path_for(site: Site, settings: Settings) -> Path:
        return resolve(settings.session_dir) / f"{site.key}.json"

    def status_path_for(site: Site, settings: Settings) -> Path:
        session_path = session_path_for(site, settings)
        return session_path.with_suffix(session_path.suffix + ".status.json")

    def site_status(site: Site, settings: Settings) -> dict:
        session_path = session_path_for(site, settings)
        status_path = status_path_for(site, settings)
        info = {
            "key": site.key,
            "label": site.label,
            "logged_in": session_path.exists(),
        }
        if session_path.exists():
            info["session_saved_at"] = session_path.stat().st_mtime
        if status_path.exists():
            try:
                info["login_progress"] = json.loads(status_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                pass
        return info

    @app.get("/")
    def index():
        settings = load_settings()
        sites = load_sites(sites_path)
        history = HistoryStore(resolve(settings.history_path))
        pending_store = PendingPostStore(resolve(settings.pending_posts_dir))
        naver_session_exists = (resolve(settings.session_dir) / "naver_blog.json").exists()

        return render_template(
            "index.html",
            settings=settings,
            sites=[site_status(site, settings) for site in sites.values()],
            posts=pending_store.list_all(),
            naver_publish_ready=naver_session_exists and bool(settings.naver_blog_id),
            today_naver_count=history.count_today(Platform.NAVER_BLOG),
            playwright_ready=is_playwright_installed(),
        )

    @app.post("/login/<site_key>")
    def start_login(site_key: str):
        settings = load_settings()
        sites = load_sites(sites_path)
        site = sites.get(site_key)
        if site is None:
            return jsonify({"error": f"알 수 없는 사이트: {site_key}"}), 404

        # 버튼을 연달아 누르거나 더블클릭하면 같은 세션 파일을 두고 경쟁하는
        # 로그인 창이 두 개 뜨면서 TargetClosedError 등 혼란스러운 실패로
        # 이어진다 - 이미 진행 중이면 새로 띄우지 않는다.
        running = active_logins.get(site_key)
        if running is not None and running.poll() is None:
            return jsonify({"error": "이미 로그인이 진행 중입니다. 기존 창을 확인해주세요."}), 409

        session_path = session_path_for(site, settings)
        session_path.parent.mkdir(parents=True, exist_ok=True)

        process = subprocess.Popen(
            [
                sys.executable,
                str(REPO_ROOT / "scripts" / "browser_login.py"),
                site.key,
                site.login_url,
                str(session_path),
            ],
            cwd=str(base_dir),
        )
        active_logins[site_key] = process
        return jsonify({"status": "started"})

    @app.get("/login/<site_key>/status")
    def login_status(site_key: str):
        settings = load_settings()
        sites = load_sites(sites_path)
        site = sites.get(site_key)
        if site is None:
            return jsonify({"error": f"알 수 없는 사이트: {site_key}"}), 404
        return jsonify(site_status(site, settings))

    @app.post("/generate")
    def generate():
        settings = load_settings()
        history = HistoryStore(resolve(settings.history_path))
        pending_store = PendingPostStore(resolve(settings.pending_posts_dir))
        keyword_term = request.form.get("keyword") or None
        interest_area = request.form.get("interest_area") or None

        try:
            post = generate_one_post(
                settings, history, keyword_term=keyword_term, interest_area=interest_area
            )
        except NoContentGeneratedError as exc:
            return jsonify({"error": str(exc)}), 400
        except Exception as exc:  # noqa: BLE001 - 원인이 무엇이든 빈 500 대신 메시지를 보여준다
            logger.exception("글 생성 중 예상치 못한 오류")
            return jsonify({"error": f"글 생성 중 오류가 발생했습니다: {exc}"}), 500

        pending = pending_store.save(post, platform="naver_blog")
        return redirect(url_for("index") + f"#post-{pending.id}")

    @app.get("/posts")
    def list_posts():
        settings = load_settings()
        pending_store = PendingPostStore(resolve(settings.pending_posts_dir))
        return jsonify([p.__dict__ for p in pending_store.list_all()])

    def control_dir_for(post_id: str, settings: Settings) -> Path:
        return resolve(settings.pending_posts_dir) / f"{post_id}.control"

    def read_control_status(control_dir: Path) -> dict:
        status_path = control_dir / "status.json"
        if not status_path.exists():
            return {"state": "not_started"}
        try:
            return json.loads(status_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {"state": "unknown"}

    def sync_pending_from_control(
        pending_store: PendingPostStore,
        history: HistoryStore,
        pending: PendingPost,
        control_status: dict,
    ) -> None:
        """자동화 스크립트가 기록한 상태를 초안 저장소/발행 이력에 반영한다.

        발행 스크립트는 백그라운드 프로세스라 Flask 쪽에 직접 콜백할 수
        없으므로, 폴링 시점에 상태 전이를 감지해 한 번만 반영한다.
        """
        state = control_status.get("state")
        if state == "published" and pending.status != "published":
            history.record(Platform.NAVER_BLOG, pending.product_id, pending.title)
            pending_store.update_status(pending.id, "published")
        elif state in ("failed", "canceled") and pending.status not in ("failed", "canceled"):
            pending_store.update_status(pending.id, state)

    @app.post("/posts/<post_id>/publish")
    def publish_post(post_id: str):
        settings = load_settings()
        history = HistoryStore(resolve(settings.history_path))
        pending_store = PendingPostStore(resolve(settings.pending_posts_dir))

        pending = pending_store.get(post_id)
        if pending is None:
            return jsonify({"error": "초안을 찾을 수 없습니다."}), 404

        if settings.dry_run:
            pending_store.update_status(post_id, "dry_run")
            return jsonify(
                {
                    "status": "dry_run",
                    "message": "연습 모드입니다. 자동 편집/발행이 시작되지 않았습니다.",
                }
            )

        if settings.kill_switch:
            return jsonify({"error": "전체 중단(kill switch)이 켜져 있어 게시할 수 없습니다."}), 409

        platform = Platform.NAVER_BLOG
        already_today = history.count_today(platform)
        cfg = settings.platforms.get("naver_blog")
        daily_cap = cfg.daily_post_cap if cfg else 1
        if already_today >= daily_cap:
            return jsonify({"error": f"오늘 네이버 게시 한도({daily_cap}건)에 도달했습니다."}), 409

        minutes_since = history.minutes_since_last_publish(platform)
        if minutes_since is not None and minutes_since < settings.min_publish_interval_min:
            wait = settings.min_publish_interval_min - minutes_since
            return (
                jsonify({"error": f"최소 발행 간격 미달입니다. {wait:.1f}분 더 기다려주세요."}),
                409,
            )

        session_path = resolve(settings.session_dir) / "naver_blog.json"
        if not session_path.exists():
            return jsonify({"error": "네이버 블로그 로그인이 필요합니다."}), 400

        if not settings.naver_blog_id:
            return (
                jsonify({"error": "config/settings.yaml에 naver_blog_id를 설정해주세요."}),
                400,
            )

        control_dir = control_dir_for(post_id, settings)
        control_dir.mkdir(parents=True, exist_ok=True)
        post_json_path = control_dir / "post.json"
        post_json_path.write_text(
            json.dumps(pending.for_automation(), ensure_ascii=False, indent=2), encoding="utf-8"
        )

        write_url = f"https://blog.naver.com/{settings.naver_blog_id}?Redirect=Write&categoryNo=0"

        subprocess.Popen(
            [
                sys.executable,
                str(REPO_ROOT / "scripts" / "naver_auto_publish.py"),
                str(post_json_path),
                str(session_path),
                str(control_dir),
                write_url,
            ],
            cwd=str(base_dir),
        )
        pending_store.update_status(post_id, "publishing")
        return jsonify({"status": "started"})

    @app.get("/posts/<post_id>/publish/status")
    def publish_status(post_id: str):
        settings = load_settings()
        history = HistoryStore(resolve(settings.history_path))
        pending_store = PendingPostStore(resolve(settings.pending_posts_dir))
        pending = pending_store.get(post_id)
        if pending is None:
            return jsonify({"error": "초안을 찾을 수 없습니다."}), 404

        control_status = read_control_status(control_dir_for(post_id, settings))
        sync_pending_from_control(pending_store, history, pending, control_status)
        return jsonify(control_status)

    @app.get("/posts/<post_id>/publish/preview")
    def publish_preview(post_id: str):
        settings = load_settings()
        preview_path = control_dir_for(post_id, settings) / "preview.png"
        if not preview_path.exists():
            return jsonify({"error": "미리보기가 아직 없습니다."}), 404
        return send_file(preview_path, mimetype="image/png")

    def _signal(post_id: str, name: str):
        settings = load_settings()
        control_dir = control_dir_for(post_id, settings)
        if not control_dir.exists():
            return jsonify({"error": "진행 중인 자동화가 없습니다."}), 404
        (control_dir / name).touch()
        return jsonify({"status": "signaled"})

    @app.post("/posts/<post_id>/publish/resume")
    def publish_resume(post_id: str):
        return _signal(post_id, "resume.signal")

    @app.post("/posts/<post_id>/publish/confirm")
    def publish_confirm(post_id: str):
        return _signal(post_id, "confirm.signal")

    @app.post("/posts/<post_id>/publish/cancel")
    def publish_cancel(post_id: str):
        return _signal(post_id, "cancel.signal")

    return app


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    ensure_playwright_ready()
    create_app().run(host="127.0.0.1", port=5000, debug=False)
