from __future__ import annotations

import logging

from blogauto.orchestrator import build_orchestrator_from_env


def main() -> int:
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )
    orchestrator = build_orchestrator_from_env()
    published = orchestrator.run_daily()
    logging.info("오늘 게시/초안 생성 완료: %d건", len(published))
    for url in published:
        logging.info(" - %s", url)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
