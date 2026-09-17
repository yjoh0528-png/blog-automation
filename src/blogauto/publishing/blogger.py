from __future__ import annotations

from typing import Any

from .base import Publisher
from ..models import Post


class BloggerPublisher(Publisher):
    """Google Blogger API(공식)를 이용한 완전 자동 발행.

    Blogger는 계정 소유자 본인의 블로그에 대해 공식 OAuth2 API로 글쓰기를
    지원하므로, 네이버/티스토리와 달리 매크로 없이 합법적으로 자동화할 수 있다.
    """

    def __init__(self, blog_id: str, credentials: Any):
        from googleapiclient.discovery import build  # 지연 임포트

        self._blog_id = blog_id
        self._service = build("blogger", "v3", credentials=credentials)

    def publish(self, post: Post) -> str:
        body = {
            "title": post.title,
            "content": post.to_html(),
            "labels": [tag for tag in post.tags if tag],
        }
        result = (
            self._service.posts()
            .insert(blogId=self._blog_id, body=body, isDraft=False)
            .execute()
        )
        return result.get("url", "")
