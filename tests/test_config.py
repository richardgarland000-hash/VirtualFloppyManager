import json

from config import Config


def test_history_is_capped_and_deduplicated(tmp_path):
    cfg = Config(str(tmp_path / "c.json"))
    for i in range(15):
        cfg.add_history(str(tmp_path / f"img{i}.img"))
    cfg.add_history(str(tmp_path / "img14.img"))      # duplicate moves to front, not added twice
    hist = cfg.get("history")
    assert len(hist) == 10
    assert hist[0].endswith("img14.img")
    assert len(set(hist)) == 10


def test_settings_roundtrip_and_defaults(tmp_path):
    path = str(tmp_path / "c.json")
    cfg = Config(path)
    assert cfg.get("auto_elevate") is True
    cfg.set("read_only", True)
    assert Config(path).get("read_only") is True


def test_corrupt_file_falls_back_to_defaults(tmp_path):
    path = tmp_path / "c.json"
    path.write_text("{ not json")
    cfg = Config(str(path))
    assert cfg.get("refresh_seconds") == 5
    assert (tmp_path / "c.json.corrupt").exists()


def test_wrong_types_ignored(tmp_path):
    path = tmp_path / "c.json"
    path.write_text(json.dumps({"refresh_seconds": "fast", "read_only": True}))
    cfg = Config(str(path))
    assert cfg.get("refresh_seconds") == 5
    assert cfg.get("read_only") is True
