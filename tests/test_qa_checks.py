from blogauto.models import Keyword, Post, Product, ProductSource, Section
from blogauto.qa.checks import run_checks


def make_post(**overrides) -> Post:
    product = Product(
        source=ProductSource.COUPANG_PARTNERS,
        product_id="p1",
        title="목 어깨 안마기",
        original_url="https://example.com/p1",
        affiliate_url="https://example.com/p1?affid=abc",
    )
    sections = overrides.get("sections") or [
        Section("핵심 특징", "이 제품은 강도 조절이 가능해서 사용감이 좋습니다."),
        Section("이런 분께 추천해요", "장시간 앉아서 일하는 직장인에게 추천합니다."),
        Section("사용 팁", "취침 전 15분 정도 사용하는 것을 추천합니다."),
        Section("정리", "가격 대비 만족스러운 선택지입니다."),
    ]
    return Post(
        title=overrides.get("title", "목 어깨 안마기 - 직장인을 위한 선물"),
        keyword=Keyword(term="거북목 완화 용품"),
        product=product,
        sections=sections,
        disclosure_text=overrides.get(
            "disclosure_text", "이 포스팅은 쿠팡 파트너스 활동의 일환으로 수수료를 제공받습니다."
        ),
    )


def test_run_checks_passes_for_valid_post():
    result = run_checks(make_post(), recent_product_ids=set())
    assert result.passed, result.errors


def test_run_checks_fails_missing_heading():
    sections = [Section("핵심 특징", "이 제품은 강도 조절이 가능해서 사용감이 좋습니다.")]
    result = run_checks(make_post(sections=sections), recent_product_ids=set())
    assert not result.passed
    assert any("소제목" in e for e in result.errors)


def test_run_checks_fails_banned_phrase():
    sections = [
        Section("핵심 특징", "이 제품은 100% 효과가 보장됩니다."),
        Section("이런 분께 추천해요", "장시간 앉아서 일하는 직장인에게 추천합니다."),
        Section("사용 팁", "취침 전 15분 정도 사용하는 것을 추천합니다."),
        Section("정리", "가격 대비 만족스러운 선택지입니다."),
    ]
    result = run_checks(make_post(sections=sections), recent_product_ids=set())
    assert not result.passed
    assert any("과장" in e for e in result.errors)


def test_run_checks_fails_duplicate_product():
    result = run_checks(make_post(), recent_product_ids={"p1"})
    assert not result.passed
    assert any("최근" in e for e in result.errors)


def test_run_checks_fails_missing_disclosure():
    result = run_checks(make_post(disclosure_text=""), recent_product_ids=set())
    assert not result.passed
    assert any("고지" in e for e in result.errors)
