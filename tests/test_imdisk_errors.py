import imdisk_backend
from config import Config
from imdisk_backend import ImDiskBackend


def backend(tmp_path):
    return ImDiskBackend(Config(str(tmp_path / "c.json")))


def test_denied_when_not_privileged_is_elevation(tmp_path):
    b = backend(tmp_path)
    b.last_privileged = False
    assert b._error("unmount", 1, "Error: Access is denied.").kind == "elevation"


def test_denied_when_privileged_means_in_use(tmp_path):
    b = backend(tmp_path)
    b.last_privileged = True
    err = b._error("unmount", 1, "Error: Access is denied.")
    assert err.kind == "in_use"
    assert "administrator" not in str(err).lower()


def test_in_use_text_detected(tmp_path):
    b = backend(tmp_path)
    b.last_privileged = False
    assert b._error("unmount", 1, "The process cannot access the file because it is being used").kind == "in_use"
