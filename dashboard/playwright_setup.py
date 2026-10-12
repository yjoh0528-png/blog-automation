from __future__ import annotations

import logging
import subprocess
import sys

logger = logging.getLogger(__name__)


def is_playwright_installed() -> bool:
    """Playwright 파이썬 패키지와 Chromium 실행 파일이 모두 준비됐는지 가볍게 확인한다.

    브라우저를 실제로 띄우지 않고 실행 파일 경로 존재 여부만 확인하므로,
    대시보드 페이지 렌더링마다 호출해도 비용이 작다.
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return False
    try:
        with sync_playwright() as p:
            from pathlib import Path

            return Path(p.chromium.executable_path).exists()
    except Exception:
        return False


def ensure_playwright_ready() -> bool:
    """Playwright/Chromium이 없으면 자동 설치를 시도한다.

    로그인 세션 캡처·네이버 자동 게시 기능에만 필요하므로, 설치에
    실패해도(네트워크 제한 등) 예외를 던지지 않고 대시보드 자체는 계속
    켜진 채로 둔다 - 실패 사실은 로그와 반환값으로만 알린다.
    """
    if is_playwright_installed():
        return True

    logger.warning("Playwright/Chromium이 준비되지 않아 자동 설치를 시도합니다...")
    try:
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "playwright"],
            check=True,
            capture_output=True,
            text=True,
            timeout=300,
        )
        subprocess.run(
            [sys.executable, "-m", "playwright", "install", "chromium"],
            check=True,
            capture_output=True,
            text=True,
            timeout=600,
        )
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        detail = exc.stderr if isinstance(exc, subprocess.CalledProcessError) else str(exc)
        logger.error(
            "Playwright 자동 설치에 실패했습니다 - 로그인/자동 게시 기능을 쓰려면 "
            "터미널에서 직접 `pip install playwright && playwright install chromium`을 "
            "실행해주세요. 원인: %s",
            detail,
        )
        return False

    ready = is_playwright_installed()
    if ready:
        logger.info("Playwright/Chromium 설치를 완료했습니다.")
    else:
        logger.error("Playwright 설치 명령은 끝났지만 Chromium 실행 파일을 찾지 못했습니다.")
    return ready
