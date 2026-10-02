"""Bounded run approval, streaming selection and resume validation."""
import hashlib
import hmac
import json
import re
from dataclasses import dataclass

from psycopg.rows import dict_row

from .contracts import document_id

ZERO_DIGEST = "0" * 64
FULL_THRESHOLD = 40_000
SHA40 = re.compile(r"^[0-9a-f]{40}$")
STRATA = frozenset({"all", "normal", "noisy_edge", "structured"})


@dataclass(frozen=True)
class SourcePlan:
    run_id: str
    source: str
    revision: str
    config: str
    split: str
    text_field: str
    seed: int
    max_scan: int
    sample_size: int
    license_ack: bool
    stratum: str = "all"

    def validate(self):
        if not self.run_id or not self.source or not self.text_field or not self.split:
            raise ValueError("run and source mapping required")
        if self.source != "manual" and not SHA40.fullmatch(self.revision):
            raise ValueError("HF revision must be a pinned 40-character commit SHA")
        if self.max_scan <= 0 or not 0 < self.sample_size <= self.max_scan or self.seed < 0:
            raise ValueError("positive bounded scan, quota and seed required")
        if not self.license_ack:
            raise ValueError("source rights acknowledgement required")
        if self.stratum not in STRATA:
            raise ValueError("unknown sampling stratum")


def fingerprint(record: object) -> str:
    """Canonical record digest for fail-closed replay, including malformed records."""
    try:
        data = json.dumps(record, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise ValueError("upstream record cannot be canonically serialized") from exc
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


def extend_digest(prior: str, ordinal: int, record_digest: str) -> str:
    return hashlib.sha256(f"{prior}:{ordinal}:{record_digest}".encode("ascii")).hexdigest()


def sample_rank(seed: int, ordinal: int, record_digest: str) -> str:
    return hashlib.sha256(f"{seed}:{ordinal}:{record_digest}".encode("ascii")).hexdigest()


def family_id(text: str) -> str:
    # Exact duplicates after whitespace normalization only; not a near-duplicate claim.
    return hashlib.sha256(" ".join(text.split()).encode("utf-8")).hexdigest()


def format_flags(text: str) -> list[str]:
    """Conservative CPU metadata; does not imply teacher type or quality."""
    flags = []
    stripped = text.lstrip()
    if stripped.startswith(("{", "[", "<")):
        flags.append("markup")
    if "|" in text and "\n" in text:
        flags.append("table")
    if any(line.lstrip().startswith(("- ", "* ")) for line in text.splitlines()):
        flags.append("list")
    if any(x in text for x in ("def ", "function ", "#include", "class ")):
        flags.append("code")
    if any(x in text for x in ("\\frac", "∑", "∫")):
        flags.append("math")
    return flags


def sampling_stratum(text: str) -> str:
    """Exclusive, deterministic content buckets; these are sampling cues, not teacher labels."""
    if format_flags(text) or text.count(":") >= 2 or re.search(r"(?m)^\s*\d+[.)]\s", text):
        return "structured"
    if (len(text) < 300 or len(text) > 4_000 or "\ufffd" in text
            or sum(not ch.isalpha() and not ch.isspace() for ch in text) / len(text) > 0.20):
        return "noisy_edge"
    return "normal"


def create_run(store, plan: SourcePlan):
    plan.validate()
    with store.connect() as conn:
        conn.execute("INSERT INTO labeling_runs(id) VALUES (%s)", (plan.run_id,))
        conn.execute("""INSERT INTO run_controls(run_id,source,revision,config,split,text_field,seed,max_scan,sample_size,license_ack,stratum)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
            (plan.run_id, plan.source, plan.revision, plan.config, plan.split, plan.text_field,
             plan.seed, plan.max_scan, plan.sample_size, plan.license_ack, plan.stratum))


def approve_run(store, run_id: str, *, supplied_full_token: str, configured_full_token: str,
                unapproved_ceiling: int):
    if not 0 < unapproved_ceiling < FULL_THRESHOLD:
        raise ValueError("unapproved ceiling must be below 40000")
    with store.connect() as conn:
        budget = conn.execute("SELECT reserved_count FROM teacher_budget WHERE id=true FOR UPDATE").fetchone()
        run = conn.execute("SELECT sample_size,status,approved FROM run_controls WHERE run_id=%s FOR UPDATE", (run_id,)).fetchone()
        if not run or run["status"] != "draft" or run["approved"]:
            raise ValueError("run is not an unapproved draft")
        total = budget["reserved_count"] + run["sample_size"]
        full = total >= unapproved_ceiling or run["sample_size"] >= FULL_THRESHOLD
        if full and (not configured_full_token or not hmac.compare_digest(supplied_full_token, configured_full_token)):
            raise PermissionError("separate large-run approval required")
        conn.execute("UPDATE teacher_budget SET reserved_count=%s WHERE id=true", (total,))
        conn.execute("UPDATE run_controls SET approved=true,full_approved=%s,approved_at=now() WHERE run_id=%s", (full, run_id))


def get_run(store, run_id: str) -> dict:
    with store.connect() as conn:
        row = conn.execute("SELECT * FROM run_controls WHERE run_id=%s", (run_id,)).fetchone()
        if not row:
            raise ValueError("unknown run")
        return row


def transition(store, run_id: str, expected: str, target: str):
    with store.connect() as conn:
        row = conn.execute("SELECT status,approved FROM run_controls WHERE run_id=%s FOR UPDATE", (run_id,)).fetchone()
        if not row or row["status"] != expected or not row["approved"]:
            raise ValueError("invalid run transition or missing approval")
        if expected == "ready" and target == "active":
            count = conn.execute("SELECT count(*) AS n FROM jobs WHERE run_id=%s", (run_id,)).fetchone()["n"]
            if not count:
                raise ValueError("empty run cannot start")
        conn.execute("UPDATE run_controls SET status=%s WHERE run_id=%s", (target, run_id))


def ingest_records(store, run_id: str, records, *, max_document_bytes: int, max_database_bytes: int,
                   max_bad_records: int = 10):
    """Only records in finite window are consumed; replay verifies whole persisted prefix."""
    run = get_run(store, run_id)
    if not run["approved"] or run["source"] == "manual":
        raise ValueError("approved HF run required")
    if run["status"] == "draft":
        transition(store, run_id, "draft", "collecting")
    elif run["status"] != "collecting":
        raise ValueError("run cannot ingest in this state")
    if run["rejected_records"] > max_bad_records:
        raise ValueError("malformed source record limit already exceeded")
    prior = ZERO_DIGEST
    seen = 0
    for ordinal, record in enumerate(records):
        if ordinal >= run["max_scan"]:
            break
        digest = fingerprint(record)
        next_digest = extend_digest(prior, ordinal, digest)
        if ordinal < run["cursor"]:
            if ordinal + 1 == run["cursor"] and next_digest != run["prefix_digest"]:
                raise ValueError("stream prefix changed; resume refused")
            prior = next_digest
            seen += 1
            continue
        if prior != run["prefix_digest"]:
            raise ValueError("stream prefix changed; resume refused")
        raw = record.get(run["text_field"]) if isinstance(record, dict) else None
        invalid = not isinstance(raw, str) or not raw.strip()
        text = raw if not invalid else None
        if text is not None and len(text.encode("utf-8")) > max_document_bytes:
            text = None
        store.consider_candidate(run, ordinal, text, digest, next_digest, max_database_bytes,
                                 invalid=invalid)
        if invalid:
            run["rejected_records"] += 1
            if run["rejected_records"] > max_bad_records:
                raise ValueError("malformed source record limit exceeded")
        run["cursor"] = ordinal + 1
        run["prefix_digest"] = next_digest
        prior = next_digest
        seen += 1
    if seen < run["max_scan"]:
        raise ValueError("stream ended before bounded scan window; sample not finalized")
    store.finalize_sample(run_id, max_database_bytes)


def stream_hf(run: dict):
    # Lazy import keeps unit tests and API runtime independent from the remote provider.
    from datasets import load_dataset

    dataset = load_dataset(run["source"], name=run["config"] or None,
                           split=run["split"], revision=run["revision"], streaming=True)
    return iter(dataset)
