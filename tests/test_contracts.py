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


@pytest.mark.parametrize("kind,scores,noise,expected", [
    ("general", {"language": 4, "coherence": 4, "information": 4, "cleanliness": 4, "structure": 4, "utility": 4}, [], "PREMIUM"),
    ("structured_data", {"language": None, "coherence": 3, "information": 4, "cleanliness": 4, "structure": 4, "utility": 3}, [], "KEEP"),
    ("general", {"language": 4, "coherence": 3, "information": 1, "cleanliness": 1, "structure": 3, "utility": 1}, ["seo_advertising"], "DROP"),
    ("conversation", {"language": 4, "coherence": 3, "information": 2, "cleanliness": 4, "structure": 3, "utility": 3}, [], "KEEP"),
    ("noise_unknown", {"language": 0, "coherence": 0, "information": 0, "cleanliness": 0, "structure": 0, "utility": 0}, ["unrelated_merge"], "DROP"),
    ("reference", {"language": 1, "coherence": 2, "information": 4, "cleanliness": 1, "structure": 2, "utility": 2}, ["encoding_ocr"], "MODEL_REPAIR"),
])
def test_acceptance_exemplars_represent_independent_observations(kind, scores, noise, expected):
    response = {"id": "doc_case", "type": kind, "q": scores, "noise": noise}
    validate_label(response, "doc_case")
    assert route(response) == expected
