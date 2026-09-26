"""Exact teacher contract and independent versioned routing policy."""
import hashlib
import json
from pathlib import Path

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[2]
SCHEMA = json.loads((ROOT / "schemas/teacher_label_v1.schema.json").read_text(encoding="utf-8"))
Draft202012Validator.check_schema(SCHEMA)
VALIDATOR = Draft202012Validator(SCHEMA)
SYSTEM_PROMPT = (ROOT / "prompts/turkish_cpt_quality_teacher_v2.txt").read_text(encoding="utf-8").rstrip("\n")
USER_TEMPLATE = (ROOT / "prompts/teacher_user_v1.txt").read_text(encoding="utf-8").rstrip("\n")
POLICY_VERSION = "turkish_cpt_routing_v1"
DETERMINISTIC_NOISE = {"boilerplate_ui", "repetition", "seo_advertising", "markup_extraction"}


def document_id(source: str, revision: str, config: str, split: str, ordinal: int, text: str) -> str:
    if not source or not revision or ordinal < 0 or not text:
        raise ValueError("source, revision, ordinal and text required")
    coordinates = json.dumps([source, revision, config, split, ordinal, hashlib.sha256(text.encode()).hexdigest()], ensure_ascii=False, separators=(",", ":"))
    return "doc_" + hashlib.sha256(coordinates.encode()).hexdigest()


def validate_label(payload: object, expected_id: str) -> dict:
    VALIDATOR.validate(payload)
    if payload["id"] != expected_id:
        raise ValueError("teacher document id mismatch")
    return payload


def route(label: dict) -> str:
    q = label["q"]
    i, n, c, u = (q[k] for k in ("information", "cleanliness", "coherence", "utility"))
    noise = set(label["noise"])
    if u == 4 and i >= 3 and n >= 3 and c >= 3:
        return "PREMIUM"
    if u >= 3 and n >= 3:
        return "KEEP"
    if i >= 3 and n <= 2 and noise and noise <= DETERMINISTIC_NOISE:
        return "DETERMINISTIC_REPAIR"
    if i >= 3 and c >= 2 and noise & {"encoding_ocr", "linguistic_corruption"} and not noise & {"truncation_fragment", "unrelated_merge"}:
        return "MODEL_REPAIR"
    if u <= 1 or (i <= 1 and n <= 1):
        return "DROP"
    return "REVIEW"


def user_prompt(doc_id: str, sketch: str) -> str:
    # The sketch is untrusted content. Source metadata is deliberately omitted.
    return USER_TEMPLATE.replace("{{doc_id}}", doc_id).replace("{{teacher_sketch}}", sketch)
