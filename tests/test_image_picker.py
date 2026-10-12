from __future__ import annotations

import requests

from blogauto.content.image_picker import pick_best_image
from blogauto.content.llm import LLMClient
from blogauto.research.models import ImageCandidate


class FakeDownloadResponse:
    def __init__(self, content_type: str, body: bytes):
        self.headers = {"content-type": content_type}
        self._body = body

    def raise_for_status(self):
        pass

    def iter_content(self, chunk_size):
        yield self._body


class RecordingLLMClient(LLMClient):
    """generate_with_images 호출 여부/인자를 기록하고, 고정된 답을 돌려준다."""

    def __init__(self, answer: str):
        self.answer = answer
        self.calls: list[tuple[str, str, list[str]]] = []

    def generate(self, system_prompt, user_prompt):
        raise AssertionError("이미지 판단에는 generate_with_images가 쓰여야 한다")

    def generate_with_images(self, system_prompt, user_prompt, image_paths):
        self.calls.append((system_prompt, user_prompt, image_paths))
        return self.answer


class BoomLLMClient(LLMClient):
    def generate(self, system_prompt, user_prompt):
        raise AssertionError

    def generate_with_images(self, system_prompt, user_prompt, image_paths):
        raise RuntimeError("비전 호출 실패")


def _mock_images(monkeypatch, by_url: dict[str, FakeDownloadResponse | Exception]):
    def fake_get(url, timeout=None, stream=None):
        result = by_url[url]
        if isinstance(result, Exception):
            raise result
        return result

    monkeypatch.setattr("blogauto.content.image_picker.requests.get", fake_get)


def test_no_candidates_returns_none():
    assert pick_best_image(RecordingLLMClient("0"), [], context="아무거나") is None


def test_single_downloadable_candidate_skips_llm_call(monkeypatch):
    candidates = [ImageCandidate(url="https://img.example.com/a.jpg")]
    _mock_images(
        monkeypatch, {"https://img.example.com/a.jpg": FakeDownloadResponse("image/jpeg", b"x")}
    )
    llm = RecordingLLMClient("0")

    choice = pick_best_image(llm, candidates, context="거북목 쿠션")

    assert choice is candidates[0]
    assert llm.calls == []


def test_llm_picks_second_candidate(monkeypatch):
    candidates = [
        ImageCandidate(url="https://img.example.com/a.jpg"),
        ImageCandidate(url="https://img.example.com/b.jpg"),
    ]
    _mock_images(
        monkeypatch,
        {
            "https://img.example.com/a.jpg": FakeDownloadResponse("image/jpeg", b"a"),
            "https://img.example.com/b.jpg": FakeDownloadResponse("image/jpeg", b"b"),
        },
    )
    llm = RecordingLLMClient("1번이 가장 적합하다")

    choice = pick_best_image(llm, candidates, context="거북목 쿠션")

    assert choice is candidates[1]
    assert len(llm.calls) == 1
    _, _, image_paths = llm.calls[0]
    assert len(image_paths) == 2


def test_llm_says_none_returns_none(monkeypatch):
    candidates = [
        ImageCandidate(url="https://img.example.com/a.jpg"),
        ImageCandidate(url="https://img.example.com/b.jpg"),
    ]
    _mock_images(
        monkeypatch,
        {
            "https://img.example.com/a.jpg": FakeDownloadResponse("image/jpeg", b"a"),
            "https://img.example.com/b.jpg": FakeDownloadResponse("image/jpeg", b"b"),
        },
    )
    llm = RecordingLLMClient("NONE")

    assert pick_best_image(llm, candidates, context="거북목 쿠션") is None


def test_non_image_content_type_is_skipped(monkeypatch):
    candidates = [
        ImageCandidate(url="https://img.example.com/a.jpg"),
        ImageCandidate(url="https://img.example.com/b.jpg"),
    ]
    _mock_images(
        monkeypatch,
        {
            "https://img.example.com/a.jpg": FakeDownloadResponse("text/html", b"<html></html>"),
            "https://img.example.com/b.jpg": FakeDownloadResponse("image/png", b"b"),
        },
    )
    llm = RecordingLLMClient("0")

    choice = pick_best_image(llm, candidates, context="거북목 쿠션")

    assert choice is candidates[1]
    assert llm.calls == []  # 다운로드 성공한 후보가 1개뿐이라 LLM 호출 생략


def test_all_downloads_fail_returns_none(monkeypatch):
    candidates = [ImageCandidate(url="https://img.example.com/a.jpg")]
    _mock_images(
        monkeypatch,
        {"https://img.example.com/a.jpg": requests.RequestException("network down")},
    )

    assert pick_best_image(RecordingLLMClient("0"), candidates, context="x") is None


def test_llm_error_falls_back_to_first_downloaded_candidate(monkeypatch):
    candidates = [
        ImageCandidate(url="https://img.example.com/a.jpg"),
        ImageCandidate(url="https://img.example.com/b.jpg"),
    ]
    _mock_images(
        monkeypatch,
        {
            "https://img.example.com/a.jpg": FakeDownloadResponse("image/jpeg", b"a"),
            "https://img.example.com/b.jpg": FakeDownloadResponse("image/jpeg", b"b"),
        },
    )

    choice = pick_best_image(BoomLLMClient(), candidates, context="x")

    assert choice is candidates[0]


def test_oversized_image_is_rejected(monkeypatch):
    big_body = b"x" * (9 * 1024 * 1024)
    candidates = [
        ImageCandidate(url="https://img.example.com/big.jpg"),
        ImageCandidate(url="https://img.example.com/ok.jpg"),
    ]
    _mock_images(
        monkeypatch,
        {
            "https://img.example.com/big.jpg": FakeDownloadResponse("image/jpeg", big_body),
            "https://img.example.com/ok.jpg": FakeDownloadResponse("image/jpeg", b"ok"),
        },
    )
    llm = RecordingLLMClient("0")

    choice = pick_best_image(llm, candidates, context="x")

    assert choice is candidates[1]
    assert llm.calls == []  # 다운로드 성공한 후보가 1개뿐이라 LLM 호출 생략
