"""범용 Playwright 로그인 세션 캡처 스크립트.

사용법:
    python scripts/browser_login.py <site> <login_url> <session_path>

headed(화면이 보이는) Chromium 브라우저를 띄워 login_url로 이동한다.
페이지에는 플로팅 "로그인 완료 - 세션 저장" 버튼이 주입되며, 사용자가
평소처럼 직접 로그인한 뒤 그 버튼을 누르면 storageState(쿠키 등)를
session_path에 저장하고 브라우저를 닫는다.

이 스크립트는 로그인 자체를 자동화하지 않는다 — 아이디/비밀번호를
코드로 입력하지 않고, 사람이 실제 브라우저 창에서 직접 로그인해야만
세션이 저장된다.

진행 상태는 `<session_path>.status.json`에 기록된다:
  waiting  -> 브라우저가 열려 사용자 로그인을 기다리는 중
  success  -> 세션 저장 완료
  timeout  -> 제한 시간(10분) 내에 로그인 완료 버튼이 눌리지 않음
  canceled -> 사용자가 브라우저 창을 직접 닫음
  error    -> 예외 발생
"""

from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

TIMEOUT_SECONDS = 600
POLL_INTERVAL_SECONDS = 0.5
BINDING_NAME = "blogautoSaveSession"

_INIT_SCRIPT_TEMPLATE = """
(() => {
    if (window.__blogautoInjected) return;
    window.__blogautoInjected = true;

    const inject = () => {
        if (!document.body || document.getElementById('__blogauto_login_btn')) return;
        const btn = document.createElement('button');
        btn.id = '__blogauto_login_btn';
        btn.textContent = '\\u2713 \\ub85c\\uadf8\\uc778 \\uc644\\ub8cc - \\uc138\\uc158 \\uc800\\uc7a5';
        btn.style.cssText = [
            'position:fixed', 'top:16px', 'right:16px', 'z-index:2147483647',
            'padding:12px 20px', 'background:#3fb27f', 'color:#fff',
            'border:none', 'border-radius:8px', 'font-size:15px',
            'font-weight:600', 'cursor:pointer',
            'box-shadow:0 2px 10px rgba(0,0,0,0.25)',
        ].join(';');
        btn.addEventListener('click', () => {
            btn.disabled = true;
            btn.textContent = '\\uc800\\uc7a5 \\uc911...';
            window.%(binding_name)s();
        });
        document.body.appendChild(btn);
    };

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', inject);
    } else {
        inject();
    }
    new MutationObserver(inject).observe(document.documentElement, {
        childList: true, subtree: true,
    });
})();
""" % {"binding_name": BINDING_NAME}


def _write_status(status_path: Path, status: str, **extra: object) -> None:
    payload = {
        "status": status,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        **extra,
    }
    status_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def capture_session(
    site: str,
    login_url: str,
    session_path: Path,
    status_path: Path,
    timeout_seconds: float = TIMEOUT_SECONDS,
    headless: bool = False,
    on_page_ready: "Callable[[object], None] | None" = None,
) -> str:
    """로그인 세션 캡처의 핵심 로직. 운영 CLI와 테스트가 공유한다.

    on_page_ready(page)는 페이지 로드+버튼 주입 직후 호출되는 훅이다.
    운영 코드(main())는 이 훅을 쓰지 않는다(사람이 실제로 로그인 후
    버튼을 누른다) - 통합 테스트에서만 "사람이 버튼을 누르는 것"을
    프로그램적으로 흉내내는 용도로 쓴다.

    반환값: "success" | "timeout" | "canceled"
    """
    from playwright.sync_api import sync_playwright  # 지연 임포트

    session_path.parent.mkdir(parents=True, exist_ok=True)
    _write_status(status_path, "waiting", site=site)

    done = {"flag": False}

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        context = browser.new_context()
        page = context.new_page()

        context.expose_binding(BINDING_NAME, lambda source: done.__setitem__("flag", True))
        context.add_init_script(_INIT_SCRIPT_TEMPLATE)

        page.goto(login_url)

        if on_page_ready is not None:
            on_page_ready(page)

        start = time.monotonic()
        result_status = "timeout"
        while time.monotonic() - start < timeout_seconds:
            if page.is_closed():
                result_status = "canceled"
                break
            if done["flag"]:
                result_status = "success"
                break
            page.wait_for_timeout(int(POLL_INTERVAL_SECONDS * 1000))

        if result_status == "success":
            context.storage_state(path=str(session_path))
            _write_status(status_path, "success", site=site)
        else:
            _write_status(status_path, result_status, site=site)

        browser.close()
        return result_status


def main() -> int:
    if len(sys.argv) != 4:
        print(
            "사용법: python scripts/browser_login.py <site> <login_url> <session_path>",
            file=sys.stderr,
        )
        return 2

    site, login_url, session_path_arg = sys.argv[1], sys.argv[2], sys.argv[3]
    session_path = Path(session_path_arg)
    status_path = session_path.with_suffix(session_path.suffix + ".status.json")
    # 환경변수로 제한 시간을 조절 가능하게 함 (자동 테스트에서 600초를
    # 기다리지 않도록 - 기본값은 TIMEOUT_SECONDS 그대로).
    timeout_seconds = float(os.environ.get("BLOGAUTO_LOGIN_TIMEOUT_SECONDS", TIMEOUT_SECONDS))

    try:
        result_status = capture_session(
            site, login_url, session_path, status_path, timeout_seconds=timeout_seconds
        )
    except Exception as exc:  # noqa: BLE001 - 스크립트 최상위: 원인을 상태 파일에 남기고 종료
        _write_status(status_path, "error", site=site, message=str(exc))
        raise

    return 0 if result_status == "success" else 1


if __name__ == "__main__":
    raise SystemExit(main())
