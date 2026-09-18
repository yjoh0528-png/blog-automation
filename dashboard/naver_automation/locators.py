from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

Strategy = Literal["role", "text", "placeholder", "label"]


@dataclass
class LocatorSpec:
    strategy: Strategy
    value: str
    role: str | None = None  # strategy == "role"일 때 함께 필요 (예: "button")


def find_first(scope, candidates: list[LocatorSpec], timeout_ms: int = 3000):
    """여러 후보 로케이터를 순서대로 시도해, 화면에 나타나는 첫 요소를 반환한다.

    scope: Playwright Page 또는 Frame (또는 같은 인터페이스를 흉내 낸 테스트 더블).
    반환값: 찾은 Locator, 전부 실패하면 None.

    네이버 에디터의 실제 DOM을 라이브로 검증할 수 없는 환경에서 작성되었기
    때문에, 아래를 호출하는 쪽의 후보 문구는 확인되지 않은 최선의 추정치다.
    호출부는 None이 돌아오면 반드시 "막힘" 상태로 전환해 사람에게 넘겨야
    한다 - 후보 중 하나가 매치됐다고 그것이 반드시 의도한 요소라는 보장은
    없으므로, 중요한 단계(발행 등)는 스크린샷으로 사람이 최종 확인하게
    한다.
    """
    for spec in candidates:
        try:
            locator = _build_locator(scope, spec).first
            locator.wait_for(state="visible", timeout=timeout_ms)
            return locator
        except Exception:
            continue
    return None


def _build_locator(scope, spec: LocatorSpec):
    if spec.strategy == "role":
        if not spec.role:
            raise ValueError("strategy='role'에는 role 필드가 필요합니다.")
        return scope.get_by_role(spec.role, name=spec.value)
    if spec.strategy == "text":
        return scope.get_by_text(spec.value, exact=False)
    if spec.strategy == "placeholder":
        return scope.get_by_placeholder(spec.value)
    if spec.strategy == "label":
        return scope.get_by_label(spec.value)
    raise ValueError(f"알 수 없는 로케이터 전략: {spec.strategy}")
