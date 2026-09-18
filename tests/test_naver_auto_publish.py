from __future__ import annotations

import threading
import time

from scripts.naver_auto_publish import AutomationStopped, ControlChannel
from dashboard.naver_automation.locators import LocatorSpec


def test_write_status_persists_json(tmp_path):
    control = ControlChannel(tmp_path / "ctl")
    control.write_status("running", "테스트 단계", message="진행 중")

    import json

    payload = json.loads((tmp_path / "ctl" / "status.json").read_text(encoding="utf-8"))
    assert payload["state"] == "running"
    assert payload["step"] == "테스트 단계"
    assert payload["message"] == "진행 중"


def test_wait_for_any_signal_returns_immediately_if_present(tmp_path):
    control_dir = tmp_path / "ctl"
    control_dir.mkdir()
    (control_dir / "confirm.signal").touch()

    control = ControlChannel(control_dir)
    result = control.wait_for_any_signal(["confirm.signal", "cancel.signal"], timeout=5)

    assert result == "confirm.signal"
    assert not (control_dir / "confirm.signal").exists()  # 소비된 시그널은 삭제됨


def test_wait_for_any_signal_times_out(tmp_path):
    control = ControlChannel(tmp_path / "ctl")

    start = time.monotonic()
    result = control.wait_for_any_signal(["resume.signal"], timeout=1)
    elapsed = time.monotonic() - start

    assert result is None
    assert elapsed >= 1


def test_wait_for_any_signal_detects_signal_created_later(tmp_path):
    control_dir = tmp_path / "ctl"
    control = ControlChannel(control_dir)

    def create_signal_soon():
        time.sleep(0.3)
        (control_dir / "resume.signal").touch()

    threading.Thread(target=create_signal_soon).start()
    result = control.wait_for_any_signal(["resume.signal"], timeout=5)

    assert result == "resume.signal"


class AlwaysMissingScope:
    def get_by_role(self, role, name):
        raise RuntimeError("not found")

    def get_by_text(self, text, exact=False):
        raise RuntimeError("not found")

    def get_by_placeholder(self, text):
        raise RuntimeError("not found")

    def get_by_label(self, text):
        raise RuntimeError("not found")


def test_require_step_raises_automation_stopped_on_cancel(tmp_path):
    control_dir = tmp_path / "ctl"
    control = ControlChannel(control_dir)

    def cancel_soon():
        # require_step은 못 찾으면 blocked 상태를 쓰고 대기한다 - status.json이
        # 쓰일 때까지 기다렸다가 cancel 시그널을 만든다.
        for _ in range(50):
            if (control_dir / "status.json").exists():
                break
            time.sleep(0.05)
        (control_dir / "cancel.signal").touch()

    threading.Thread(target=cancel_soon).start()

    try:
        control.require_step(
            AlwaysMissingScope(),
            [LocatorSpec(strategy="text", value="제목")],
            "제목 입력",
            "못 찾음",
        )
        assert False, "AutomationStopped가 발생해야 합니다"
    except AutomationStopped as stopped:
        assert stopped.state == "canceled"
        assert stopped.step == "제목 입력"
