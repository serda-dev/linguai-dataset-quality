import json

import pytest

from linguai_quality.contracts import SYSTEM_PROMPT
from linguai_quality.teacher import TeacherClient


class FakeResponse:
    def __init__(self, content):
        self.content = content

    def raise_for_status(self):
        pass

    def json(self):
        return {"choices": [{"message": {"content": self.content}}]}


def test_teacher_sends_exact_prompt_and_rejects_mismatched_id(monkeypatch):
    sent = {}

    class FakeClient:
        def __init__(self, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def post(self, url, headers, json):
            sent.update(url=url, headers=headers, request=json)
            return FakeResponse(__import__("json").dumps({"id": "wrong", "type": "code", "q": {
                "language": None, "coherence": 4, "information": 4, "cleanliness": 4,
                "structure": 4, "utility": 4}, "noise": []}))

    monkeypatch.setattr("linguai_quality.teacher.httpx.Client", FakeClient)
    with pytest.raises(ValueError, match="document id mismatch"):
        TeacherClient("http://mock/v1", "test-secret", "mock-model").label("doc_requested", "def foo(): pass")
    assert sent["request"]["messages"][0]["content"] == SYSTEM_PROMPT
    assert "def foo(): pass" in sent["request"]["messages"][1]["content"]
    assert "source_dataset" not in sent["request"]["messages"][1]["content"]
    assert sent["headers"]["Authorization"] == "Bearer test-secret"
