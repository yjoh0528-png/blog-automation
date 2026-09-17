import pytest

from blogauto.disclosure import get_disclosure
from blogauto.models import ProductSource


def test_get_disclosure_returns_text_for_each_known_source():
    for source in ProductSource:
        text = get_disclosure(source)
        assert text
        assert "수수료" in text


def test_get_disclosure_raises_for_unknown_source():
    with pytest.raises(ValueError):
        get_disclosure("unknown")  # type: ignore[arg-type]
