from __future__ import annotations

from dataclasses import dataclass


@dataclass
class SourceArticle:
    """글감 발굴용 참고 자료 (뉴스/인기 블로그 검색 결과 1건).

    본문 전체가 아니라 제목+요약만 담는다 - 콘텐츠 생성 시 원문을
    그대로 베끼지 않고 트렌드/관심사만 참고하도록 하기 위함.
    """

    title: str
    description: str
    link: str
    source_type: str  # "news" | "blog"


@dataclass
class ImageCandidate:
    """본문 대표 이미지 후보 1건 (제휴 상품 공식 이미지 또는 이미지 검색 결과)."""

    url: str
    title: str = ""
    width: int | None = None
    height: int | None = None
