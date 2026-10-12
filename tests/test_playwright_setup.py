from __future__ import annotations

import subprocess

from dashboard import playwright_setup


def test_is_playwright_installed_false_when_import_fails(monkeypatch):
    import builtins

    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "playwright.sync_api" or name.startswith("playwright"):
            raise ImportError("no playwright")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)

    assert playwright_setup.is_playwright_installed() is False


def test_ensure_playwright_ready_skips_install_when_already_ready(monkeypatch):
    monkeypatch.setattr(playwright_setup, "is_playwright_installed", lambda: True)

    called = {"run": False}

    def fake_run(*args, **kwargs):
        called["run"] = True

    monkeypatch.setattr(playwright_setup.subprocess, "run", fake_run)

    assert playwright_setup.ensure_playwright_ready() is True
    assert called["run"] is False


def test_ensure_playwright_ready_installs_when_missing_then_succeeds(monkeypatch):
    calls = []

    def fake_run(cmd, **kwargs):
        calls.append(cmd)
        return subprocess.CompletedProcess(cmd, 0)

    # 첫 호출(설치 전 확인)은 False, 설치 명령 실행 후 재확인은 True를 반환.
    results = iter([False, True])
    monkeypatch.setattr(playwright_setup, "is_playwright_installed", lambda: next(results))
    monkeypatch.setattr(playwright_setup.subprocess, "run", fake_run)

    assert playwright_setup.ensure_playwright_ready() is True
    assert len(calls) == 2
    assert "pip" in calls[0]
    assert "chromium" in calls[1]


def test_ensure_playwright_ready_returns_false_when_install_fails(monkeypatch):
    monkeypatch.setattr(playwright_setup, "is_playwright_installed", lambda: False)

    def fake_run(cmd, **kwargs):
        raise subprocess.CalledProcessError(1, cmd, stderr="network blocked")

    monkeypatch.setattr(playwright_setup.subprocess, "run", fake_run)

    assert playwright_setup.ensure_playwright_ready() is False
