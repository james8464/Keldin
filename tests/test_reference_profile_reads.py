"""Canonical reference verification can reuse parsed, identical source bytes."""

from __future__ import annotations

import json
import os

import pytest

from Backend.Core import reference_demand


def test_repeated_verification_parses_same_source_only_once(tmp_path, monkeypatch):
    source = tmp_path / "reference-profiles.json"
    source.write_bytes(reference_demand.PROFILES_PATH.read_bytes())
    monkeypatch.setattr(reference_demand, "PROFILES_PATH", source)
    real_loads = json.loads
    parsed = []
    monkeypatch.setattr(reference_demand, "_profile_source_index", None, raising=False)

    def counted_loads(value, *args, **kwargs):
        parsed.append(len(value))
        return real_loads(value, *args, **kwargs)

    original = reference_demand.profile_for("aqa/economics", "3")
    monkeypatch.setattr(reference_demand.json, "loads", counted_loads)
    for _ in range(3):
        assert reference_demand.profile_for_verified_context(original) is original
    assert len(parsed) == 1


def test_canonical_reference_changes_invalidate_prior_context(tmp_path, monkeypatch):
    source = tmp_path / "reference-profiles.json"
    raw = reference_demand.PROFILES_PATH.read_bytes()
    source.write_bytes(raw)
    monkeypatch.setattr(reference_demand, "PROFILES_PATH", source)
    original = reference_demand.profile_for("aqa/economics", "3")
    assert reference_demand.profile_for_verified_context(original) is original

    modified = json.loads(raw)
    record = next(
        profile
        for profile in modified["profiles"]
        if (profile["family_id"], profile["paper_id"]) == ("aqa/economics", "3")
    )
    fingerprint = record["source_fingerprint"].encode()
    replacement = b"f" * len(fingerprint)
    assert replacement != fingerprint
    changed = raw.replace(fingerprint, replacement, 1)
    before = source.stat()
    source.write_bytes(changed)
    os.utime(source, ns=(before.st_atime_ns, before.st_mtime_ns))
    assert source.stat().st_size == before.st_size
    assert source.stat().st_mtime_ns == before.st_mtime_ns
    with pytest.raises(ValueError, match="canonical reference evidence"):
        reference_demand.profile_for_verified_context(original)

    source.write_bytes(raw)
    assert reference_demand.profile_for_verified_context(original) is original
    source.unlink()
    with pytest.raises(ValueError, match="canonical reference evidence"):
        reference_demand.profile_for_verified_context(original)


@pytest.mark.parametrize("corruption", ["duplicate", "invalid_utf8"])
def test_invalid_source_never_reuses_a_previously_verified_index(
    tmp_path, monkeypatch, corruption
):
    source = tmp_path / "reference-profiles.json"
    source.write_bytes(reference_demand.PROFILES_PATH.read_bytes())
    monkeypatch.setattr(reference_demand, "PROFILES_PATH", source)
    original = reference_demand.profile_for("aqa/economics", "3")
    assert reference_demand.profile_for_verified_context(original) is original

    if corruption == "duplicate":
        payload = json.loads(source.read_bytes())
        payload["profiles"].append(payload["profiles"][0])
        source.write_text(json.dumps(payload), encoding="utf-8")
    else:
        source.write_bytes(b"\xff")
    with pytest.raises(ValueError, match="canonical reference evidence"):
        reference_demand.profile_for_verified_context(original)
