from __future__ import annotations

import json
import logging
import subprocess
import sys
import tempfile
from pathlib import Path

from flask import Flask, jsonify, redirect, render_template, request, url_for

from blogauto.config import Settings
from blogauto.history.store import HistoryStore
from blogauto.models import Platform

from .generate import NoContentGeneratedError, generate_one_post
from .pending_posts import PendingPostStore
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

        return render_template(
            "index.html",
            settings=settings,
            sites=[site_status(site, settings) for site in sites.values()],
            posts=pending_store.list_all(),
            naver_publish_ready=resolve(settings.naver_post_script_path).exists(),
            today_naver_count=history.count_today(Platform.NAVER_BLOG),
        )

    @app.post("/login/<site_key>")
    def start_login(site_key: str):
        settings = load_settings()
        sites = load_sites(sites_path)
        site = sites.get(site_key)
        if site is None:
            return jsonify({"error": f"알 수 없는 사이트: {site_key}"}), 404

        session_path = session_path_for(site, settings)
        session_path.parent.mkdir(parents=True, exist_ok=True)

        subprocess.Popen(
            [
                sys.executable,
                str(REPO_ROOT / "scripts" / "browser_login.py"),
                site.key,
                site.login_url,
                str(session_path),
            ],
            cwd=str(base_dir),
        )
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

        try:
            post = generate_one_post(settings, history, keyword_term=keyword_term)
        except NoContentGeneratedError as exc:
            return jsonify({"error": str(exc)}), 400

        pending = pending_store.save(post, platform="naver_blog")
        return redirect(url_for("index") + f"#post-{pending.id}")

    @app.get("/posts")
    def list_posts():
        settings = load_settings()
        pending_store = PendingPostStore(resolve(settings.pending_posts_dir))
        return jsonify([p.__dict__ for p in pending_store.list_all()])

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
                    "message": "연습 모드입니다. 실제로 게시되지 않았습니다.",
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

        script_path = resolve(settings.naver_post_script_path)
        if not script_path.exists():
            return (
                jsonify(
                    {
                        "error": (
                            "녹화된 네이버 게시 스크립트가 없습니다. "
                            f"playwright codegen으로 녹화해 {script_path}에 저장해주세요."
                        )
                    }
                ),
                400,
            )

        session_path = resolve(settings.session_dir) / "naver_blog.json"
        if not session_path.exists():
            return jsonify({"error": "네이버 블로그 로그인이 필요합니다."}), 400

        with tempfile.TemporaryDirectory() as tmp_dir:
            title_file = Path(tmp_dir) / "title.txt"
            content_file = Path(tmp_dir) / "content.html"
            title_file.write_text(pending.title, encoding="utf-8")
            content_file.write_text(pending.html, encoding="utf-8")

            result = subprocess.run(
                [
                    sys.executable,
                    str(REPO_ROOT / "scripts" / "replay_post.py"),
                    str(script_path),
                    str(title_file),
                    str(content_file),
                ],
                cwd=str(base_dir),
                capture_output=True,
                text=True,
            )

        if result.returncode != 0:
            pending_store.update_status(post_id, "failed")
            logger.error("네이버 게시 실패: %s", result.stderr)
            return (
                jsonify({"error": "게시 스크립트 실행이 실패했습니다.", "detail": result.stderr[-2000:]}),
                500,
            )

        history.record(platform, pending.product_id, pending.title)
        pending_store.update_status(post_id, "published")
        return jsonify({"status": "published"})

    return app


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    create_app().run(host="127.0.0.1", port=5000, debug=False)
