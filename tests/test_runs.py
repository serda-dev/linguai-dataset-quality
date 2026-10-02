import sys
import types

import pytest

from linguai_quality.runs import SourcePlan, ZERO_DIGEST, extend_digest, fingerprint, format_flags, sample_rank, sampling_stratum, stream_hf, ingest_records


def test_source_contract_and_reproducible_rank():
    p = SourcePlan("r", "dataset/repo", "a"*40, "cfg", "train", "text", 9, 100, 10, True)
    p.validate()
    with pytest.raises(ValueError):
        SourcePlan("r", "dataset/repo", "main", "cfg", "train", "text", 9, 100, 10, True).validate()
    record = fingerprint({"text":"Örnek", "x": 3})
    assert sample_rank(9, 3, record) == sample_rank(9, 3, record)
    assert sample_rank(9, 3, record) != sample_rank(10, 3, record)
    assert extend_digest("0"*64, 0, record) != extend_digest("0"*64, 1, record)
    assert "code" in format_flags("def test(): pass")
    assert sampling_stratum("Normal bir Türkçe paragraf. " * 20) == "normal"
    assert sampling_stratum("Bozuk") == "noisy_edge"
    assert sampling_stratum("def hesapla():\n    return 1") == "structured"
    with pytest.raises(ValueError, match="stratum"):
        SourcePlan("r", "dataset/repo", "a"*40, "cfg", "train", "text", 9, 100, 10, True, "unknown").validate()


def test_hf_adapter_uses_streaming_pinned_revision(monkeypatch):
    observed = {}

    def load_dataset(path, **kwargs):
        observed.update(path=path, **kwargs)
        return iter([{"text": "x"}])

    monkeypatch.setitem(sys.modules, "datasets", types.SimpleNamespace(load_dataset=load_dataset))
    run = {"source": "fixture/approved", "config": "cfg", "split": "train", "revision": "a"*40}
    assert list(stream_hf(run)) == [{"text": "x"}]
    assert observed == {"path": "fixture/approved", "name": "cfg", "split": "train",
                        "revision": "a"*40, "streaming": True}


def test_interrupted_stream_replay_refuses_changed_prefix(monkeypatch):
    run = {"run_id": "r", "source": "fixture/hf", "revision": "a"*40, "config": "", "split": "train",
           "text_field": "text", "seed": 17, "max_scan": 3, "sample_size": 1,
           "approved": True, "status": "collecting", "cursor": 0,
           "prefix_digest": ZERO_DIGEST, "rejected_records": 0}

    class FakeStore:
        def __init__(self):
            self.rows = []
            self.finalized = False

        def consider_candidate(self, state, ordinal, text, digest, next_digest, max_database_bytes, *, invalid=False):
            self.rows.append(text)

        def finalize_sample(self, run_id, max_database_bytes):
            self.finalized = True

    store = FakeStore()
    monkeypatch.setattr("linguai_quality.runs.get_run", lambda _store, _id: run)
    records = [{"text": "bir"}, {"text": "iki"}, {"text": "üç"}]

    def interrupted():
        yield records[0]
        yield records[1]
        raise OSError("network lost")

    with pytest.raises(OSError):
        ingest_records(store, "r", interrupted(), max_document_bytes=100, max_database_bytes=1000)
    assert run["cursor"] == 2 and not store.finalized
    with pytest.raises(ValueError, match="prefix changed"):
        ingest_records(store, "r", [{"text": "changed"}, *records[1:]],
                       max_document_bytes=100, max_database_bytes=1000)
    assert store.rows == ["bir", "iki"] and run["cursor"] == 2
    ingest_records(store, "r", records, max_document_bytes=100, max_database_bytes=1000)
    assert store.rows == ["bir", "iki", "üç"] and store.finalized
