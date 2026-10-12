"""네이버 블로그 에디터에 글을 자동 입력하고, 사람이 확인한 뒤 발행한다.

사용법:
    python scripts/naver_auto_publish.py <post_json> <session_path> <control_dir> <write_url>

post_json: {"title", "sections": [{"heading","body"}, ...], "image_url",
            "product_link", "disclosure_text"} 형태의 파일.
session_path: 네이버 로그인 storageState 파일 (대시보드 로그인으로 생성됨).
control_dir: 진행 상태(status.json)와 사람의 개입 신호(resume/confirm/
             cancel .signal 파일), 미리보기 스크린샷(preview.png)을 주고받는
             디렉터리. 대시보드가 이 디렉터리를 폴링/제어한다.
write_url: 네이버 블로그 글쓰기 페이지 URL.

핵심 안전장치:
  - 실제 "발행" 버튼은 사람이 대시보드에서 확인 후 confirm.signal을 만들어야
    눌린다 (연습 모드가 아니어도).
  - 네이버 에디터의 정확한 DOM 구조는 이 환경에서 검증할 수 없었다. 그래서
    CSS 클래스명이 아니라 버튼 텍스트/role처럼 비교적 안정적인 신호로 요소를
    찾고(`dashboard.naver_automation.locators.find_first`), 그마저 못 찾으면
    자동화를 멈추고 사람에게 넘긴다(brower 창은 항상 보이는 상태).
"""

from __future__ import annotations

import json
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO_ROOT))

from dashboard.naver_automation.locators import LocatorSpec, find_first  # noqa: E402

SIGNAL_WAIT_TIMEOUT = 1800  # 30분: 사람의 확인/개입을 기다리는 최대 시간
POLL_INTERVAL = 1.0

# 아래 후보 문구는 네이버 스마트에디터를 라이브로 검증하지 못한 채 작성된
# 최선의 추정치다. 실제로 맞지 않으면 자동으로 "막힘" 상태가 되어 사람에게
# 넘어간다 - 틀린 곳을 잘못 눌러 사고가 나는 것보다 안전하게 실패하도록
# 설계했다.
TITLE_CANDIDATES = [
    LocatorSpec(strategy="placeholder", value="제목"),
    LocatorSpec(strategy="role", role="textbox", value="제목"),
]
BODY_CANDIDATES = [
    LocatorSpec(strategy="placeholder", value="본문"),
    LocatorSpec(strategy="role", role="textbox", value="본문"),
]
RESTORE_CANCEL_CANDIDATES = [
    LocatorSpec(strategy="role", role="button", value="취소"),
    LocatorSpec(strategy="text", value="취소"),
]
IMAGE_BUTTON_CANDIDATES = [
    LocatorSpec(strategy="role", role="button", value="사진"),
    LocatorSpec(strategy="text", value="사진"),
    LocatorSpec(strategy="role", role="button", value="이미지"),
]
PUBLISH_BUTTON_CANDIDATES = [
    LocatorSpec(strategy="role", role="button", value="발행"),
    LocatorSpec(strategy="text", value="발행"),
]


class AutomationStopped(Exception):
    def __init__(self, state: str, step: str, message: str | None = None):
        super().__init__(message or step)
        self.state = state
        self.step = step
        self.message = message


class ControlChannel:
    """status.json 기록 + resume/confirm/cancel 시그널 파일 대기."""

    def __init__(self, control_dir: Path, signal_wait_timeout: float = SIGNAL_WAIT_TIMEOUT):
        self.dir = control_dir
        self.dir.mkdir(parents=True, exist_ok=True)
        self.signal_wait_timeout = signal_wait_timeout

    def write_status(self, state: str, step: str, message: str | None = None, **extra):
        payload = {
            "state": state,
            "step": step,
            "message": message,
            "updated_at": datetime.now(timezone.utc).isoformat(),
            **extra,
        }
        (self.dir / "status.json").write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    def wait_for_any_signal(self, names: list[str], timeout: float | None = None) -> str | None:
        if timeout is None:
            timeout = self.signal_wait_timeout
        start = time.monotonic()
        while True:
            for name in names:
                path = self.dir / name
                if path.exists():
                    path.unlink(missing_ok=True)
                    return name
            if time.monotonic() - start > timeout:
                return None
            time.sleep(POLL_INTERVAL)

    def require_step(self, scope, candidates: list[LocatorSpec], step: str, hint: str):
        """요소를 찾을 때까지 시도하고, 실패하면 사람에게 넘겼다가 재개한다."""
        while True:
            found = find_first(scope, candidates)
            if found is not None:
                return found
            self.write_status("blocked", step=step, message=hint)
            signal = self.wait_for_any_signal(["resume.signal", "cancel.signal"])
            if signal == "cancel.signal":
                raise AutomationStopped("canceled", step)
            if signal is None:
                raise AutomationStopped("failed", step, f"{hint} (시간 초과)")
            self.write_status("running", step=step, message="사용자 개입 후 재개")


def run_automation(
    post: dict,
    session_path: str | Path,
    control: ControlChannel,
    write_url: str,
    headless: bool = False,
) -> int:
    """자동 편집 + 사람 확인 대기 + 발행의 핵심 로직. CLI와 테스트가 공유한다."""
    import requests
    from playwright.sync_api import sync_playwright

    control.write_status("running", "브라우저 시작")

    with sync_playwright() as p:
        try:
            browser = p.chromium.launch(headless=headless)
        except Exception as exc:  # noqa: BLE001 - 브라우저 자체가 없으면 명확히 실패 보고
            control.write_status(
                "failed", "브라우저 시작",
                f"Playwright 브라우저를 실행하지 못했습니다: {exc}. "
                "'playwright install chromium'을 먼저 실행했는지 확인하세요.",
            )
            return 1

        context = browser.new_context(storage_state=str(session_path))
        page = context.new_page()

        pending_upload: dict[str, str | None] = {"path": None}

        def on_filechooser(chooser):
            if pending_upload["path"]:
                chooser.set_files(pending_upload["path"])

        page.on("filechooser", on_filechooser)

        try:
            control.write_status("running", "에디터 접속")
            page.goto(write_url)
            page.wait_for_timeout(2500)

            frame = page.frame_locator("iframe#mainFrame")

            # 작성 중이던 글 복원 팝업은 있을 수도 없을 수도 있다 - 없으면
            # 정상이므로 막힘 처리하지 않고 그냥 넘어간다.
            cancel_btn = find_first(frame, RESTORE_CANCEL_CANDIDATES, timeout_ms=2000)
            if cancel_btn is not None:
                cancel_btn.click()
                page.wait_for_timeout(500)

            control.write_status("running", "제목 입력")
            title_field = control.require_step(
                frame, TITLE_CANDIDATES, "제목 입력",
                "제목 입력창을 찾지 못했습니다. 브라우저에서 직접 제목 칸을 클릭한 뒤 [계속]을 눌러주세요.",
            )
            title_field.click()
            page.keyboard.type(post["title"], delay=8)

            control.write_status("running", "본문 입력")
            page.keyboard.press("Enter")
            body_field = find_first(frame, BODY_CANDIDATES, timeout_ms=2000)
            if body_field is not None:
                body_field.click()

            for section in post.get("sections", []):
                page.keyboard.type(section["heading"], delay=8)
                page.keyboard.press("Enter")
                page.keyboard.type(section["body"], delay=6)
                page.keyboard.press("Enter")
                page.keyboard.press("Enter")

            # 제휴 고지 문구는 법적으로 반드시 본문에 표시되어야 한다 - 절대
            # 생략하지 않는다 (src/blogauto/disclosure.py 참고).
            if post.get("product_link"):
                page.keyboard.type(f"상품 보러 가기: {post['product_link']}", delay=6)
                page.keyboard.press("Enter")
                page.keyboard.press("Enter")
            if post.get("disclosure_text"):
                page.keyboard.type(post["disclosure_text"], delay=6)
                page.keyboard.press("Enter")

            if post.get("image_url"):
                control.write_status("running", "이미지 다운로드")
                try:
                    tmp_dir = Path(tempfile.mkdtemp())
                    image_path = tmp_dir / "product.jpg"
                    resp = requests.get(post["image_url"], timeout=15)
                    resp.raise_for_status()
                    image_path.write_bytes(resp.content)

                    control.write_status("running", "이미지 삽입")
                    image_btn = control.require_step(
                        frame, IMAGE_BUTTON_CANDIDATES, "이미지 삽입",
                        "이미지 삽입 버튼을 찾지 못했습니다. 브라우저에서 직접 이미지를 넣은 뒤 [계속]을 눌러주세요.",
                    )
                    pending_upload["path"] = str(image_path)
                    image_btn.click()
                    page.wait_for_timeout(3000)
                    pending_upload["path"] = None
                except AutomationStopped:
                    raise
                except Exception as exc:  # noqa: BLE001 - 이미지 실패는 발행을 막지 않는다
                    control.write_status("running", "이미지 삽입 건너뜀", message=str(exc))

            control.write_status("running", "미리보기 생성")
            screenshot_path = control.dir / "preview.png"
            page.screenshot(path=str(screenshot_path), full_page=True)

            control.write_status(
                "awaiting_confirmation", "발행 확인 대기", screenshot="preview.png"
            )
            signal = control.wait_for_any_signal(["confirm.signal", "cancel.signal"])
            if signal == "cancel.signal":
                raise AutomationStopped("canceled", "발행 확인 대기")
            if signal is None:
                raise AutomationStopped("failed", "발행 확인 대기", "시간 초과")

            control.write_status("running", "발행 처리 중")
            publish_btn = control.require_step(
                page, PUBLISH_BUTTON_CANDIDATES, "발행 버튼",
                "발행 버튼을 찾지 못했습니다. 브라우저에서 직접 발행을 눌러주세요. "
                "발행 후 [계속]을 누르면 완료 처리됩니다.",
            )
            publish_btn.click()
            page.wait_for_timeout(2500)

            final_url = page.url
            if "blog.naver.com" in final_url and any(ch.isdigit() for ch in final_url):
                control.write_status("published", "완료", url=final_url)
                return 0
            control.write_status(
                "failed", "발행 확인 실패",
                f"발행 후 URL이 게시글 주소로 보이지 않습니다: {final_url}",
            )
            return 1

        except AutomationStopped as stopped:
            control.write_status(stopped.state, stopped.step, stopped.message)
            return 0 if stopped.state == "canceled" else 1
        except Exception as exc:  # noqa: BLE001 - 예상 못한 오류도 대시보드에 보이게 남긴다
            control.write_status("failed", "예상치 못한 오류", str(exc))
            return 1
        finally:
            browser.close()


def main() -> int:
    if len(sys.argv) != 5:
        print(
            "사용법: python scripts/naver_auto_publish.py <post_json> <session_path> "
            "<control_dir> <write_url>",
            file=sys.stderr,
        )
        return 2

    post_json_path, session_path, control_dir_arg, write_url = sys.argv[1:5]
    post = json.loads(Path(post_json_path).read_text(encoding="utf-8"))
    control = ControlChannel(Path(control_dir_arg))

    return run_automation(post, session_path, control, write_url, headless=False)


if __name__ == "__main__":
    raise SystemExit(main())
