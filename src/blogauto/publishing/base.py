from __future__ import annotations

from abc import ABC, abstractmethod

from ..models import Post


class Publisher(ABC):
    @abstractmethod
    def publish(self, post: Post) -> str:
        """게시 후 결과 URL(또는 초안 파일 경로)을 반환한다."""
