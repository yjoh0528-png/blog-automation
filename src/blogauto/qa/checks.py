from __future__ import annotations

from dataclasses import dataclass, field

from ..models import Post
from ..policy import BANNED_PHRASES, REQUIRED_SECTION_HEADINGS

_MIN_SECTION_CHARS = 15


@dataclass
class CheckResult:
    passed: bool
    errors: list[str] = field(default_factory=list)


def run_checks(post: Post, recent_product_ids: set[str]) -> CheckResult:
    errors: list[str] = []

    headings = {s.heading for s in post.sections}
    missing = [h for h in REQUIRED_SECTION_HEADINGS if h not in headings]
    if missing:
        errors.append(f"필수 소제목 누락: {missing}")

    for section in post.sections:
        if len(section.body) < _MIN_SECTION_CHARS:
            errors.append(f"'{section.heading}' 섹션이 너무 짧습니다 ({len(section.body)}자)")
        for phrase in BANNED_PHRASES:
            if phrase.lower() in section.body.lower():
                errors.append(f"'{section.heading}' 섹션에 과장 광고 표현 포함: '{phrase}'")

    if not post.disclosure_text:
        errors.append("제휴 고지 문구가 없습니다")

    if not post.product.link:
        errors.append("상품 링크가 비어 있습니다")

    if post.product.product_id in recent_product_ids:
        errors.append(f"최근에 이미 다룬 상품입니다: {post.product.product_id}")

    return CheckResult(passed=not errors, errors=errors)
