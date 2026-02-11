import json
from pathlib import Path
from scrape_midieval import build_manifest


def test_build_manifest(tmp_path):
    """Build manifest from date directories."""
    for date, desc in [("2026-02-11", "Desc A"), ("2026-02-10", "Desc B")]:
        d = tmp_path / date
        d.mkdir()
        meta = {"scale": "Test", "root": "C", "tempo": 120, "description": desc}
        (d / "meta.json").write_text(json.dumps(meta))
        (d / "preview.ogg").write_bytes(b"fake")

    manifest = build_manifest(tmp_path)
    assert len(manifest) == 2
    assert manifest[0]["date"] == "2026-02-11"  # newest first
    assert manifest[1]["date"] == "2026-02-10"
    assert manifest[0]["description"] == "Desc A"
