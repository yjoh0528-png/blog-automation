"""사용자가 녹화한 네이버 게시 스크립트를 실행한다.

사용법:
    python scripts/replay_post.py <recorded_script.py> <title_file> <content_file>

recorded_script.py는 아래 명령으로 사용자가 직접 1회 녹화한 스크립트다:

    playwright codegen --load-storage=data/sessions/naver_blog.json \\
        https://blog.naver.com/<본인아이디>?Redirect=Write

녹화 중 입력했던 샘플 제목/본문 텍스트는, 녹화가 끝난 뒤 각각
`os.environ["BLOGAUTO_TITLE"]`, `os.environ["BLOGAUTO_CONTENT"]`로
직접 바꿔두어야 한다 (README의 "네이버 게시 스크립트 녹화" 절 참고).

이 러너는 네이버 에디터의 셀렉터를 전혀 알지 못한다 — 실제 클릭/입력
동작은 전부 사용자가 녹화한 스크립트 안에 있다. 여기서는 제목/본문을
환경변수로 넘기고 그 스크립트를 그대로 실행할 뿐이다.

제목/본문을 스크립트 소스에 문자열로 직접 치환하지 않는 이유: 내용에
따옴표나 특수문자가 섞이면 Python 문법이 깨질 수 있다. 그래서 값 전달은
항상 환경변수로 한다.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

TIMEOUT_SECONDS = 300


def main() -> int:
    if len(sys.argv) != 4:
        print(
            "사용법: python scripts/replay_post.py <recorded_script.py> <title_file> <content_file>",
            file=sys.stderr,
        )
        return 2

    script_path = Path(sys.argv[1])
    if not script_path.exists():
        print(f"녹화된 스크립트를 찾을 수 없습니다: {script_path}", file=sys.stderr)
        return 2

    title = Path(sys.argv[2]).read_text(encoding="utf-8")
    content = Path(sys.argv[3]).read_text(encoding="utf-8")

    env = os.environ.copy()
    env["BLOGAUTO_TITLE"] = title
    env["BLOGAUTO_CONTENT"] = content

    try:
        result = subprocess.run(
            [sys.executable, str(script_path)],
            capture_output=True,
            text=True,
            timeout=TIMEOUT_SECONDS,
            env=env,
        )
    except subprocess.TimeoutExpired:
        print(f"게시 스크립트가 {TIMEOUT_SECONDS}초 내에 끝나지 않았습니다.", file=sys.stderr)
        return 1

    sys.stdout.write(result.stdout)
    sys.stderr.write(result.stderr)
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
