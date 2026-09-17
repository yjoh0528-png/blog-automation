from blogauto.config import PlatformConfig, Settings
from blogauto.content.generator import ContentGenerator
from blogauto.content.llm import TemplateLLMClient
from blogauto.history.store import HistoryStore
from blogauto.keyword_research.seed_provider import SeedKeywordProvider
from blogauto.models import Platform, Product, ProductSource
from blogauto.orchestrator import Orchestrator
from blogauto.publishing.base import Publisher


class FakeProductSource:
    def __init__(self, products):
        self._products = products

    def search(self, keyword, limit=10):
        return self._products


class FakePublisher(Publisher):
    def __init__(self):
        self.published = []

    def publish(self, post):
        self.published.append(post)
        return f"https://fake.example/{post.product.product_id}"


def make_settings(tmp_path, daily_post_cap=1):
    return Settings(
        seed_keywords=["거북목 완화 용품"],
        target_audience_map={"거북목 완화 용품": "직장인"},
        platforms={
            "google_blogger": PlatformConfig(enabled=True, daily_post_cap=daily_post_cap)
        },
        history_path=str(tmp_path / "history.json"),
    )


def make_product(product_id="p1") -> Product:
    return Product(
        source=ProductSource.COUPANG_PARTNERS,
        product_id=product_id,
        title="목 어깨 안마기",
        original_url=f"https://example.com/{product_id}",
    )


def test_run_daily_publishes_within_cap(tmp_path):
    settings = make_settings(tmp_path)
    publisher = FakePublisher()
    orchestrator = Orchestrator(
        settings=settings,
        keyword_provider=SeedKeywordProvider(),
        product_sources=[FakeProductSource([make_product("p1")])],
        generator=ContentGenerator(TemplateLLMClient()),
        publishers={Platform.GOOGLE_BLOGGER: publisher},
        history=HistoryStore(settings.history_path),
    )

    results = orchestrator.run_daily()

    assert len(results) == 1
    assert len(publisher.published) == 1
    assert publisher.published[0].product.product_id == "p1"


def test_run_daily_respects_daily_cap_already_reached(tmp_path):
    settings = make_settings(tmp_path, daily_post_cap=1)
    history = HistoryStore(settings.history_path)
    history.record(Platform.GOOGLE_BLOGGER, "already", "이미 게시된 글")

    publisher = FakePublisher()
    orchestrator = Orchestrator(
        settings=settings,
        keyword_provider=SeedKeywordProvider(),
        product_sources=[FakeProductSource([make_product("p2")])],
        generator=ContentGenerator(TemplateLLMClient()),
        publishers={Platform.GOOGLE_BLOGGER: publisher},
        history=history,
    )

    results = orchestrator.run_daily()

    assert results == []
    assert publisher.published == []


def test_run_daily_avoids_recently_used_product(tmp_path):
    settings = make_settings(tmp_path, daily_post_cap=1)
    history = HistoryStore(settings.history_path)
    # 다른 플랫폼(티스토리)에서 이미 다룬 상품은 구글 블로거에서도 중복으로 취급되어야 한다.
    history.record(Platform.TISTORY, "p1", "티스토리에서 이미 다룬 상품")

    publisher = FakePublisher()
    orchestrator = Orchestrator(
        settings=settings,
        keyword_provider=SeedKeywordProvider(),
        product_sources=[FakeProductSource([make_product("p1")])],
        generator=ContentGenerator(TemplateLLMClient()),
        publishers={Platform.GOOGLE_BLOGGER: publisher},
        history=history,
    )

    results = orchestrator.run_daily()

    # 구글 블로거의 오늘 게시 카운트는 0이므로 시도는 하지만, p1이 최근 이력에 있어
    # 재사용할 다른 상품이 없어 결과적으로 게시되지 않아야 한다.
    assert results == []
    assert publisher.published == []
