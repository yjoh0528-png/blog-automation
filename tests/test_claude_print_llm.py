from __future__ import annotations

import json
import subprocess

import pytest

from blogauto.content.llm import ClaudeCliError, ClaudePrintModeLLMClient


def _completed(stdout: str = "", returncode: int = 0, stderr: str = "") -> subprocess.CompletedProcess:
    return subprocess.CompletedProcess(args=[], returncode=returncode, stdout=stdout, stderr=stderr)


def test_generate_resolves_binary_via_which_for_windows_cmd_shim(monkeypatch):
    """Windows에서 npm으로 설치된 claude CLI는 실제로 claude.cmd라서, PATH에
    있어도 subprocess.run(["claude", ...])은 shell=True 없이 찾지 못한다.
    shutil.which로 미리 해석한 절대경로를 넘겨야 한다."""
    captured = {}

    monkeypatch.setattr(
        "blogauto.content.llm.shutil.which", lambda binary: r"C:\npm\claude.cmd"
    )

    def fake_run(cmd, **kwargs):
        captured["cmd"] = cmd
        return _completed(stdout=json.dumps({"result": "ok", "is_error": False}))

    monkeypatch.setattr("blogauto.content.llm.subprocess.run", fake_run)

    client = ClaudePrintModeLLMClient()
    result = client.generate("sys", "user")

    assert result == "ok"
    assert captured["cmd"][0] == r"C:\npm\claude.cmd"


def test_generate_falls_back_to_raw_binary_name_when_which_fails(monkeypatch):
    monkeypatch.setattr("blogauto.content.llm.shutil.which", lambda binary: None)

    captured = {}

    def fake_run(cmd, **kwargs):
        captured["cmd"] = cmd
        return _completed(stdout=json.dumps({"result": "ok", "is_error": False}))

    monkeypatch.setattr("blogauto.content.llm.subprocess.run", fake_run)

    client = ClaudePrintModeLLMClient(binary="claude")
    client.generate("sys", "user")

    assert captured["cmd"][0] == "claude"


def test_generate_raises_clear_error_when_binary_not_found(monkeypatch):
    monkeypatch.setattr("blogauto.content.llm.shutil.which", lambda binary: None)

    def fake_run(cmd, **kwargs):
        raise FileNotFoundError("not found")

    monkeypatch.setattr("blogauto.content.llm.subprocess.run", fake_run)

    client = ClaudePrintModeLLMClient(binary="claude")
    with pytest.raises(ClaudeCliError, match="실행 파일을 찾을 수 없습니다"):
        client.generate("sys", "user")


def test_generate_raises_on_timeout(monkeypatch):
    monkeypatch.setattr("blogauto.content.llm.shutil.which", lambda binary: "/usr/bin/claude")

    def fake_run(cmd, **kwargs):
        raise subprocess.TimeoutExpired(cmd=cmd, timeout=1)

    monkeypatch.setattr("blogauto.content.llm.subprocess.run", fake_run)

    client = ClaudePrintModeLLMClient(timeout=1)
    with pytest.raises(ClaudeCliError, match="초 내에 오지 않았습니다"):
        client.generate("sys", "user")


def test_generate_raises_on_nonzero_exit_code(monkeypatch):
    monkeypatch.setattr("blogauto.content.llm.shutil.which", lambda binary: "/usr/bin/claude")
    monkeypatch.setattr(
        "blogauto.content.llm.subprocess.run",
        lambda cmd, **kwargs: _completed(returncode=1, stderr="로그인이 필요합니다"),
    )

    client = ClaudePrintModeLLMClient()
    with pytest.raises(ClaudeCliError, match="로그인이 필요합니다"):
        client.generate("sys", "user")


def test_generate_raises_on_invalid_json(monkeypatch):
    monkeypatch.setattr("blogauto.content.llm.shutil.which", lambda binary: "/usr/bin/claude")
    monkeypatch.setattr(
        "blogauto.content.llm.subprocess.run",
        lambda cmd, **kwargs: _completed(stdout="이것은 JSON이 아닙니다"),
    )

    client = ClaudePrintModeLLMClient()
    with pytest.raises(ClaudeCliError, match="JSON 파싱 실패"):
        client.generate("sys", "user")


def test_generate_raises_when_payload_reports_error(monkeypatch):
    monkeypatch.setattr("blogauto.content.llm.shutil.which", lambda binary: "/usr/bin/claude")
    monkeypatch.setattr(
        "blogauto.content.llm.subprocess.run",
        lambda cmd, **kwargs: _completed(
            stdout=json.dumps({"is_error": True, "result": "사용량 한도 초과"})
        ),
    )

    client = ClaudePrintModeLLMClient()
    with pytest.raises(ClaudeCliError, match="사용량 한도 초과"):
        client.generate("sys", "user")


def test_generate_with_images_includes_paths_in_prompt(monkeypatch):
    monkeypatch.setattr("blogauto.content.llm.shutil.which", lambda binary: "/usr/bin/claude")
    captured = {}

    def fake_run(cmd, **kwargs):
        captured["prompt"] = cmd[2]  # ["claude", "-p", <prompt>, ...]
        return _completed(stdout=json.dumps({"result": "1", "is_error": False}))

    monkeypatch.setattr("blogauto.content.llm.subprocess.run", fake_run)

    client = ClaudePrintModeLLMClient()
    result = client.generate_with_images("sys", "고르세요", ["/tmp/a.jpg", "/tmp/b.jpg"])

    assert result == "1"
    assert "/tmp/a.jpg" in captured["prompt"]
    assert "/tmp/b.jpg" in captured["prompt"]
