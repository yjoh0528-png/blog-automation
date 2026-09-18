from __future__ import annotations

import pytest

from dashboard.naver_automation.locators import LocatorSpec, find_first


class FakeLocator:
    def __init__(self, name: str, visible: bool):
        self.name = name
        self._visible = visible

    @property
    def first(self):
        return self

    def wait_for(self, state: str, timeout: int):
        if not self._visible:
            raise TimeoutError(f"{self.name} not visible within {timeout}ms")


class FakeScope:
    """get_by_role/text/placeholder/label을 흉내 낸 테스트 더블."""

    def __init__(self, visible_names: set[str]):
        self._visible_names = visible_names

    def get_by_role(self, role, name):
        return FakeLocator(f"role:{role}:{name}", name in self._visible_names)

    def get_by_text(self, text, exact=False):
        return FakeLocator(f"text:{text}", text in self._visible_names)

    def get_by_placeholder(self, text):
        return FakeLocator(f"placeholder:{text}", text in self._visible_names)

    def get_by_label(self, text):
        return FakeLocator(f"label:{text}", text in self._visible_names)


def test_find_first_returns_first_visible_candidate():
    scope = FakeScope({"발행"})
    candidates = [
        LocatorSpec(strategy="role", role="button", value="게시"),
        LocatorSpec(strategy="text", value="발행"),
    ]

    result = find_first(scope, candidates)

    assert result is not None
    assert result.name == "text:발행"


def test_find_first_tries_candidates_in_order():
    scope = FakeScope({"게시", "발행"})
    candidates = [
        LocatorSpec(strategy="role", role="button", value="게시"),
        LocatorSpec(strategy="text", value="발행"),
    ]

    result = find_first(scope, candidates)

    assert result.name == "role:button:게시"


def test_find_first_returns_none_when_no_candidate_matches():
    scope = FakeScope(set())
    candidates = [
        LocatorSpec(strategy="text", value="발행"),
        LocatorSpec(strategy="placeholder", value="제목을 입력하세요"),
    ]

    assert find_first(scope, candidates) is None


def test_find_first_skips_candidate_that_raises():
    class RaisingScope(FakeScope):
        def get_by_role(self, role, name):
            raise RuntimeError("boom")

    scope = RaisingScope({"발행"})
    candidates = [
        LocatorSpec(strategy="role", role="button", value="게시"),
        LocatorSpec(strategy="text", value="발행"),
    ]

    result = find_first(scope, candidates)

    assert result.name == "text:발행"


def test_locator_spec_role_strategy_requires_role_field():
    scope = FakeScope({"게시"})
    candidates = [LocatorSpec(strategy="role", value="게시")]  # role 필드 누락

    # role 없이 호출하면 내부에서 ValueError -> find_first가 삼키고 다음 후보로 넘어가
    # 결과적으로 None을 반환해야 한다 (조용히 잘못된 값을 쓰지 않음).
    assert find_first(scope, candidates) is None
