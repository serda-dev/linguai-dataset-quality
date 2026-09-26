import copy
import json

import pytest
from jsonschema import ValidationError

from linguai_quality.contracts import document_id, route, user_prompt, validate_label


def label(doc_id="doc_a", **scores):
    return {"id": doc_id, "type": "code", "q": dict(language=None, coherence=4, information=4,
            cleanliness=1, structure=4, utility=3, **scores), "noise": ["boilerplate_ui"]}


def test_identity_is_stable_but_sensitive_to_revision_and_original_text():
    a = document_id("source", "rev1", "cfg", "train", 7, "özgün")
    assert a == document_id("source", "rev1", "cfg", "train", 7, "özgün")
    assert a != document_id("source", "rev2", "cfg", "train", 7, "özgün")
    assert a != document_id("source", "rev1", "cfg", "train", 7, "özgün ")


def test_schema_id_and_independent_routing():
    original = label()
    before = copy.deepcopy(original)
    assert validate_label(original, "doc_a") == original
    assert route(original) == "DETERMINISTIC_REPAIR"
    assert original == before
    with pytest.raises(ValueError):
        validate_label(original, "doc_b")
    with pytest.raises(ValidationError):
        validate_label({**original, "reasoning": "unwanted"}, "doc_a")
    with pytest.raises(ValidationError):
        validate_label({**original, "noise": ["boilerplate_ui", "boilerplate_ui"]}, "doc_a")


def test_mixed_unsafe_noise_requires_review_and_no_rewrite():
    noisy = label()
    noisy["noise"].append("unrelated_merge")
    assert route(noisy) == "REVIEW"


def test_teacher_payload_does_not_add_source_and_keeps_sketch():
    sketch = "Doğal Türkçe örnek"
    result = user_prompt("doc_a", sketch)
    assert "DOCUMENT_ID:\ndoc_a" in result
    assert "<<<DOCUMENT\n" + sketch + "\nDOCUMENT" in result
    assert "source_dataset" not in result
