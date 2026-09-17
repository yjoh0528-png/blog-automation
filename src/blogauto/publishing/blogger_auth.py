from __future__ import annotations

from typing import Any

from ..config import env


def load_blogger_credentials() -> Any:
    """GitHub Actions처럼 비대화형인 환경을 위해 refresh token 기반으로 자격증명을 구성한다.

    사전에 로컬에서 OAuth 동의 화면을 한 번 통과시켜 refresh token을 발급받아
    BLOGGER_REFRESH_TOKEN 시크릿으로 등록해두어야 한다.
    """
    from google.oauth2.credentials import Credentials  # 지연 임포트

    return Credentials(
        token=None,
        refresh_token=env("BLOGGER_REFRESH_TOKEN", required=True),
        client_id=env("BLOGGER_CLIENT_ID", required=True),
        client_secret=env("BLOGGER_CLIENT_SECRET", required=True),
        token_uri="https://oauth2.googleapis.com/token",
        scopes=["https://www.googleapis.com/auth/blogger"],
    )
