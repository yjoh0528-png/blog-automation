"""제휴/광고 고지 문구.

관련 법규: 표시광고법 및 공정거래위원회 "추천보증 등에 관한 표시광고 심사지침"은
경제적 대가를 받고 작성한 콘텐츠에 그 사실을 명확히 표시할 것을 요구한다.
쿠팡 파트너스는 별도로 의무 고지 문구를 지정하고 있다.

주의: 아래 문구, 특히 네이버 쇼핑커넥트/오늘의집 큐레이터 문구는 각 프로그램의
최신 운영 정책에 따라 바뀔 수 있으므로, 실제 운영 전 각 파트너센터 공지사항에서
최신 문구를 반드시 재확인할 것.
"""

from __future__ import annotations

from .models import ProductSource

_DISCLOSURES: dict[ProductSource, str] = {
    ProductSource.COUPANG_PARTNERS: (
        "이 포스팅은 쿠팡 파트너스 활동의 일환으로, 이에 따른 일정액의 수수료를 제공받습니다."
    ),
    ProductSource.NAVER_SHOPPING_CONNECT: (
        "이 포스팅은 네이버 쇼핑커넥트를 통해 일정액의 수수료를 제공받을 수 있습니다."
    ),
    ProductSource.OHOUSE_CURATOR: (
        "이 포스팅은 오늘의집 큐레이터 활동을 통해 일정액의 수수료를 제공받을 수 있습니다."
    ),
}


def get_disclosure(source: ProductSource) -> str:
    try:
        return _DISCLOSURES[source]
    except KeyError as exc:
        raise ValueError(f"등록되지 않은 제휴 소스: {source}") from exc
