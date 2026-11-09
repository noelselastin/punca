import json

import pytest

from llm.client import LLMClient, LLMUnavailable
from llm.schemas import MapResult


class FakeClient(LLMClient):
    """LLMClient whose network call is replaced: models listed in `busy` raise a 503."""

    def __init__(self, busy):
        super().__init__(offline=True)
        self._client = object()  # pretend a client exists
        self.models = ["primary-model", "fallback-model"]
        self.busy = set(busy)
        self.calls = []

    def _call(self, model, prompt, schema, temperature):
        self.calls.append(model)
        if model in self.busy:
            raise RuntimeError("503 UNAVAILABLE. This model is currently experiencing high demand.")
        return json.dumps({"conceptId": "chain-rule", "justification": "test", "confidence": 0.9})


def test_falls_back_and_cools_down_busy_model():
    c = FakeClient(busy={"primary-model"})
    assert c.generate_json("p", MapResult, 0.1)["conceptId"] == "chain-rule"
    assert c.last_model == "fallback-model"
    c.generate_json("p", MapResult, 0.1)
    assert c.calls == ["primary-model", "fallback-model", "fallback-model"]  # primary skipped while cooling down


def test_all_busy_raises_unavailable():
    c = FakeClient(busy={"primary-model", "fallback-model"})
    with pytest.raises(LLMUnavailable):
        c.generate_json("p", MapResult, 0.1)


def test_non_transient_errors_are_not_swallowed():
    c = FakeClient(busy=set())
    c._call = lambda *a: (_ for _ in ()).throw(ValueError("400 INVALID_ARGUMENT schema"))
    with pytest.raises(ValueError):
        c.generate_json("p", MapResult, 0.1)
