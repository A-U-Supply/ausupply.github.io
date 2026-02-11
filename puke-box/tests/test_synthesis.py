import json
from pathlib import Path
from scrape_midieval import build_manifest


def test_build_manifest(tmp_path):
    """Build manifest from date directories."""
    for date, desc in [("2026-02-11", "Desc A"), ("2026-02-10", "Desc B")]:
        d = tmp_path / date
        d.mkdir()
        meta = {"scale": "Test", "root": "C", "tempo": 120, "description": desc, "date": date}
        (d / "meta.json").write_text(json.dumps(meta))
        (d / "preview.ogg").write_bytes(b"fake")

    manifest = build_manifest(tmp_path)
    assert len(manifest) == 2
    assert manifest[0]["id"] == "2026-02-11"  # newest first
    assert manifest[1]["id"] == "2026-02-10"
    assert manifest[0]["date"] == "2026-02-11"
    assert manifest[0]["description"] == "Desc A"


def test_build_manifest_with_timestamp_dirs(tmp_path):
    """Build manifest from YYYY-MM-DD-HHMMSS directories."""
    entries = [
        ("2026-02-11-160000", "2026-02-11", "Desc A"),
        ("2026-02-11-080000", "2026-02-11", "Desc B"),
        ("2026-02-10-160000", "2026-02-10", "Desc C"),
    ]
    for entry_id, date, desc in entries:
        d = tmp_path / entry_id
        d.mkdir()
        meta = {"scale": "Test", "root": "C", "tempo": 120, "description": desc, "date": date}
        (d / "meta.json").write_text(json.dumps(meta))
        (d / "preview.ogg").write_bytes(b"fake")

    manifest = build_manifest(tmp_path)
    assert len(manifest) == 3
    assert manifest[0]["id"] == "2026-02-11-160000"  # newest first
    assert manifest[1]["id"] == "2026-02-11-080000"
    assert manifest[2]["id"] == "2026-02-10-160000"
    assert manifest[0]["date"] == "2026-02-11"
    assert manifest[1]["date"] == "2026-02-11"
