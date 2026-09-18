"""실제 Playwright 브라우저로 자동화 메커니즘을 검증하는 통합 테스트.

실제 네이버 사이트에는 접근할 수 없으므로(네트워크 제한), 로컬 HTML
픽스처(tests/fixtures/)를 대상으로 실행한다. 이 테스트들은 "네이버 실제
화면과 100% 맞는다"를 증명하지 않는다 - "로그인 세션 캡처, 리질리언트
로케이터, 제어파일 프로토콜(막힘/재개/확인/취소, 발행 성공 판정)이라는
메커니즘 자체가 진짜 브라우저에서 실제로 동작한다"는 것을 증명한다.

Chromium 브라우저 바이너리가 없는 환경(예: 이 저장소를 처음 체크아웃한
CI)에서는 자동으로 건너뛴다.
"""

from __future__ import annotations

import http.server
import json
import threading
import time
from pathlib import Path

import pytest

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"


class _CookieLoginHandler(http.server.BaseHTTPRequestHandler):
    """Set-Cookie 헤더로 실제 쿠키를 내려주는 최소 로그인 페이지.

    data: URL은 브라우저 정책상 쿠키를 아예 가질 수 없어(Chromium:
    "Cookies are disabled inside 'data:' URLs") 세션 캡처 테스트에 쓸 수
    없다 - 실제 origin이 있는 로컬 HTTP 서버가 필요하다.
    """

    def do_GET(self):  # noqa: N802 - http.server가 요구하는 이름
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Set-Cookie", "blogauto_test=1; Path=/")
        self.end_headers()
        self.wfile.write(b"<h1>fake login page</h1>")

    def log_message(self, format, *args):  # noqa: A002 - 테스트 출력 조용히
        pass


@pytest.fixture
def local_login_server():
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _CookieLoginHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}/"
    finally:
        server.shutdown()
        thread.join(timeout=5)


def _playwright_browser_available() -> bool:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return False
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            browser.close()
        return True
    except Exception:
        return False


pytestmark = pytest.mark.skipif(
    not _playwright_browser_available(),
    reason="Playwright Chromium 브라우저를 이 환경에서 실행할 수 없습니다 "
    "('playwright install chromium' 필요, 또는 버전 불일치).",
)


def _wait_for_state(control_dir: Path, states: set[str], timeout: float = 20.0) -> dict:
    status_path = control_dir / "status.json"
    start = time.monotonic()
    while time.monotonic() - start < timeout:
        if status_path.exists():
            try:
                data = json.loads(status_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                data = {}
            if data.get("state") in states:
                return data
        time.sleep(0.2)
    raise AssertionError(
        f"{timeout}초 내에 상태 {states}에 도달하지 못했습니다. "
        f"마지막 상태: {status_path.read_text(encoding='utf-8') if status_path.exists() else '(없음)'}"
    )


class TestBrowserLoginCapture:
    def test_capture_session_saves_cookies_after_simulated_click(
        self, tmp_path, local_login_server
    ):
        from scripts.browser_login import capture_session

        session_path = tmp_path / "session.json"
        status_path = tmp_path / "session.json.status.json"

        login_url = local_login_server

        def simulate_user_click(page):
            # 실제로는 사람이 로그인 후 주입된 버튼을 누른다. 테스트에서는
            # 같은 버튼을 프로그램적으로 눌러 "사람이 눌렀다"를 흉내낸다.
            page.wait_for_selector("#__blogauto_login_btn", timeout=5000)
            page.click("#__blogauto_login_btn")

        result = capture_session(
            site="test_site",
            login_url=login_url,
            session_path=session_path,
            status_path=status_path,
            timeout_seconds=15,
            headless=True,
            on_page_ready=simulate_user_click,
        )

        assert result == "success"
        assert session_path.exists()

        saved = json.loads(session_path.read_text(encoding="utf-8"))
        cookie_names = {c["name"] for c in saved.get("cookies", [])}
        assert "blogauto_test" in cookie_names

        status = json.loads(status_path.read_text(encoding="utf-8"))
        assert status["status"] == "success"

    def test_capture_session_times_out_without_click(self, tmp_path):
        from scripts.browser_login import capture_session

        session_path = tmp_path / "session.json"
        status_path = tmp_path / "session.json.status.json"

        result = capture_session(
            site="test_site",
            login_url="data:text/html,<h1>no button click happens</h1>",
            session_path=session_path,
            status_path=status_path,
            timeout_seconds=2,
            headless=True,
        )

        assert result == "timeout"
        assert not session_path.exists()


class TestNaverAutoPublishHappyPath:
    def test_run_automation_completes_full_flow(self, tmp_path):
        from scripts.naver_auto_publish import ControlChannel, run_automation

        # 세션 파일은 storage_state 인자로만 쓰이므로 빈 유효 JSON이면 된다.
        session_path = tmp_path / "session.json"
        session_path.write_text(json.dumps({"cookies": [], "origins": []}), encoding="utf-8")

        control_dir = tmp_path / "control"
        control = ControlChannel(control_dir, signal_wait_timeout=20)

        write_url = f"file://{FIXTURES_DIR / 'fake_naver_editor.html'}"
        post = {
            "title": "테스트 제목입니다",
            "sections": [
                {"heading": "핵심 특징", "body": "테스트 본문 내용입니다."},
            ],
            "image_url": None,
            "product_link": "https://example.com/product",
            "disclosure_text": "이 포스팅은 테스트 고지 문구입니다.",
        }

        result_holder: dict[str, int] = {}

        def run():
            result_holder["code"] = run_automation(
                post, session_path, control, write_url, headless=True
            )

        thread = threading.Thread(target=run)
        thread.start()

        status = _wait_for_state(control_dir, {"awaiting_confirmation", "failed"})
        assert status["state"] == "awaiting_confirmation", status
        assert (control_dir / "preview.png").exists()

        (control_dir / "confirm.signal").touch()
        thread.join(timeout=20)
        assert not thread.is_alive(), "run_automation이 제시간에 끝나지 않았습니다"

        final_status = json.loads((control_dir / "status.json").read_text(encoding="utf-8"))
        assert final_status["state"] == "published", final_status
        assert "blog.naver.com" in final_status["url"]
        assert result_holder["code"] == 0

    def test_run_automation_cancel_during_confirmation(self, tmp_path):
        from scripts.naver_auto_publish import ControlChannel, run_automation

        session_path = tmp_path / "session.json"
        session_path.write_text(json.dumps({"cookies": [], "origins": []}), encoding="utf-8")

        control_dir = tmp_path / "control"
        control = ControlChannel(control_dir, signal_wait_timeout=20)
        write_url = f"file://{FIXTURES_DIR / 'fake_naver_editor.html'}"
        post = {"title": "취소 테스트", "sections": [{"heading": "핵심 특징", "body": "본문"}]}

        result_holder: dict[str, int] = {}

        def run():
            result_holder["code"] = run_automation(
                post, session_path, control, write_url, headless=True
            )

        thread = threading.Thread(target=run)
        thread.start()

        _wait_for_state(control_dir, {"awaiting_confirmation", "failed"})
        (control_dir / "cancel.signal").touch()
        thread.join(timeout=20)
        assert not thread.is_alive()

        final_status = json.loads((control_dir / "status.json").read_text(encoding="utf-8"))
        assert final_status["state"] == "canceled", final_status
        assert result_holder["code"] == 0


class TestNaverAutoPublishBlockedPath:
    def test_run_automation_blocks_when_title_missing_then_cancels(self, tmp_path):
        from scripts.naver_auto_publish import ControlChannel, run_automation

        session_path = tmp_path / "session.json"
        session_path.write_text(json.dumps({"cookies": [], "origins": []}), encoding="utf-8")

        control_dir = tmp_path / "control"
        control = ControlChannel(control_dir, signal_wait_timeout=20)
        write_url = f"file://{FIXTURES_DIR / 'fake_naver_editor_no_title.html'}"
        post = {"title": "제목 없음 테스트", "sections": []}

        result_holder: dict[str, int] = {}

        def run():
            result_holder["code"] = run_automation(
                post, session_path, control, write_url, headless=True
            )

        thread = threading.Thread(target=run)
        thread.start()

        status = _wait_for_state(control_dir, {"blocked"})
        assert status["step"] == "제목 입력"
        assert "찾지 못했습니다" in status["message"]

        (control_dir / "cancel.signal").touch()
        thread.join(timeout=20)
        assert not thread.is_alive()

        final_status = json.loads((control_dir / "status.json").read_text(encoding="utf-8"))
        assert final_status["state"] == "canceled"
        assert final_status["step"] == "제목 입력"
        assert result_holder["code"] == 0


class TestNaverAutoPublishBrowserFailure:
    def test_run_automation_reports_clear_failure_when_browser_missing(self, tmp_path, monkeypatch):
        from scripts.naver_auto_publish import ControlChannel, run_automation

        session_path = tmp_path / "session.json"
        session_path.write_text(json.dumps({"cookies": [], "origins": []}), encoding="utf-8")
        control_dir = tmp_path / "control"
        control = ControlChannel(control_dir, signal_wait_timeout=5)

        # 존재하지 않는 브라우저 채널을 강제해 launch() 자체가 실패하게 만든다.
        monkeypatch.setenv("PLAYWRIGHT_BROWSERS_PATH", str(tmp_path / "no_such_browsers_dir"))

        code = run_automation(
            {"title": "x", "sections": []},
            session_path,
            control,
            f"file://{FIXTURES_DIR / 'fake_naver_editor.html'}",
            headless=True,
        )

        assert code == 1
        final_status = json.loads((control_dir / "status.json").read_text(encoding="utf-8"))
        assert final_status["state"] == "failed"
        assert final_status["step"] == "브라우저 시작"
        assert "playwright install chromium" in final_status["message"]


class TestNaverAutoPublishRealSubprocess:
    """dashboard/app.py가 실제로 하는 것과 동일하게, CLI를 subprocess로
    실행해 main()의 argv 파싱 -> run_automation() 연결까지 검증한다.
    (이전 테스트들은 run_automation()을 직접 호출했다 - 이 테스트는 그
    바깥의 CLI 진입점까지 포함한다.) main()은 headless=False로 고정되어
    있어 화면이 필요하므로 xvfb-run으로 감싼다.
    """

    def test_cli_subprocess_completes_via_control_files(self, tmp_path):
        import shutil
        import subprocess
        import sys

        if shutil.which("xvfb-run") is None:
            pytest.skip("xvfb-run이 없어 headless=False CLI를 검증할 수 없습니다.")

        session_path = tmp_path / "session.json"
        session_path.write_text(json.dumps({"cookies": [], "origins": []}), encoding="utf-8")

        control_dir = tmp_path / "control"
        post_path = tmp_path / "post.json"
        post_path.write_text(
            json.dumps({"title": "서브프로세스 테스트", "sections": [{"heading": "핵심 특징", "body": "본문"}]}),
            encoding="utf-8",
        )

        repo_root = Path(__file__).resolve().parent.parent
        write_url = f"file://{FIXTURES_DIR / 'fake_naver_editor.html'}"

        proc = subprocess.Popen(
            [
                "xvfb-run", "-a",
                sys.executable, str(repo_root / "scripts" / "naver_auto_publish.py"),
                str(post_path), str(session_path), str(control_dir), write_url,
            ],
            cwd=str(repo_root),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        try:
            status = _wait_for_state(control_dir, {"awaiting_confirmation", "failed"}, timeout=30)
            assert status["state"] == "awaiting_confirmation", status
            (control_dir / "confirm.signal").touch()

            returncode = proc.wait(timeout=30)
            final_status = json.loads((control_dir / "status.json").read_text(encoding="utf-8"))
            assert final_status["state"] == "published", (final_status, proc.stderr.read())
            assert returncode == 0
        finally:
            if proc.poll() is None:
                proc.kill()


class TestBrowserLoginRealSubprocess:
    """dashboard/app.py의 POST /login/<site>가 실제로 실행하는 것과 동일한
    subprocess 호출(main()의 argv 파싱까지 포함)을 검증한다."""

    def test_cli_subprocess_times_out_cleanly_without_click(self, tmp_path):
        import os
        import shutil
        import subprocess
        import sys

        if shutil.which("xvfb-run") is None:
            pytest.skip("xvfb-run이 없어 headless=False CLI를 검증할 수 없습니다.")

        session_path = tmp_path / "session.json"
        status_path = session_path.with_suffix(session_path.suffix + ".status.json")
        repo_root = Path(__file__).resolve().parent.parent

        env = {**os.environ, "BLOGAUTO_LOGIN_TIMEOUT_SECONDS": "3"}
        proc = subprocess.run(
            [
                "xvfb-run", "-a",
                sys.executable, str(repo_root / "scripts" / "browser_login.py"),
                "test_site", "data:text/html,<h1>no click</h1>", str(session_path),
            ],
            cwd=str(repo_root),
            capture_output=True,
            text=True,
            timeout=30,
            env=env,
        )

        status = json.loads(status_path.read_text(encoding="utf-8"))
        assert status["status"] == "timeout", (status, proc.stderr)
        assert proc.returncode == 1
        assert not session_path.exists()
