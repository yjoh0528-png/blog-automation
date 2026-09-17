from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum


class ProductSource(str, Enum):
    COUPANG_PARTNERS = "coupang_partners"
    NAVER_SHOPPING_CONNECT = "naver_shopping_connect"
    OHOUSE_CURATOR = "ohouse_curator"


class Platform(str, Enum):
    GOOGLE_BLOGGER = "google_blogger"
    NAVER_BLOG = "naver_blog"
    TISTORY = "tistory"


@dataclass
class Keyword:
    term: str
    score: float = 0.0
    category: str | None = None


@dataclass
class Product:
    source: ProductSource
    product_id: str
    title: str
    original_url: str
    price: int | None = None
    image_url: str | None = None
    category: str | None = None
    affiliate_url: str | None = None

    @property
    def link(self) -> str:
        return self.affiliate_url or self.original_url


@dataclass
class Section:
    heading: str
    body: str


@dataclass
class Post:
    title: str
    keyword: Keyword
    product: Product
    sections: list[Section]
    disclosure_text: str
    tags: list[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_markdown(self) -> str:
        lines = [f"# {self.title}", ""]
        for section in self.sections:
            lines.append(f"## {section.heading}")
            lines.append("")
            lines.append(section.body)
            lines.append("")
        lines.append(f"[\U0001f449 상품 보러 가기]({self.product.link})")
        lines.append("")
        lines.append(self.disclosure_text)
        return "\n".join(lines)

    def to_html(self) -> str:
        parts = [f"<h1>{self.title}</h1>"]
        for section in self.sections:
            parts.append(f"<h2>{section.heading}</h2>")
            for para in section.body.split("\n\n"):
                para = para.strip()
                if para:
                    parts.append(f"<p>{para}</p>")
        parts.append(
            f'<p><a href="{self.product.link}" rel="sponsored nofollow" target="_blank">'
            "\U0001f449 상품 보러 가기</a></p>"
        )
        parts.append(f"<p><small>{self.disclosure_text}</small></p>")
        return "\n".join(parts)
