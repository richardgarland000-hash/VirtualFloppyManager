import os

import pytest

import mount_manager
from config import Config
from mount_manager import MountManager


class FakeBackend:
    """Pretends to be ImDisk: mounting makes the letter 'exist'."""
    def __init__(self, used):
        self.used = used
        self.mounted = []

    def mount(self, image, letter, read_only, removable, floppy):
        self.mounted.append((os.path.basename(image), letter))
        self.used.add(letter)

    def is_device(self, letter):
        return False


@pytest.fixture
def env(tmp_path, monkeypatch):
    used = set()
    monkeypatch.setattr(mount_manager, "used_letters", lambda: set(used))
    monkeypatch.setattr(mount_manager, "available_letters",
                        lambda: [c for c in "ABCDEFGHIJKLMNOPQRSTUVWXYZ" if c not in used])
    monkeypatch.setattr(mount_manager, "wait_for_drive", lambda letter, present, **kw: True)
    monkeypatch.setattr(mount_manager, "notify_shell", lambda letter, added: None)
    backend = FakeBackend(used)
    mgr = MountManager(Config(str(tmp_path / "c.json")), backend)

    def image(name):
        p = tmp_path / name
        p.write_bytes(bytes(1474560))
        return str(p)

    return mgr, backend, used, image


def test_set_startup_adds_and_removes(env):
    mgr, _, _, image = env
    a = image("a.img")
    mgr.set_startup(a, "E", True)
    assert mgr.is_startup_image(a)
    assert mgr.startup_entries() == [{"image": os.path.abspath(a), "letter": "E"}]
    mgr.set_startup(a, "E", False)
    assert not mgr.is_startup_image(a)


def test_one_entry_per_letter_and_per_image(env):
    mgr, _, _, image = env
    a, b = image("a.img"), image("b.img")
    mgr.set_startup(a, "E", True)
    mgr.set_startup(b, "E", True)                    # same letter: replaces a
    assert [os.path.basename(e["image"]) for e in mgr.startup_entries()] == ["b.img"]
    mgr.set_startup(b, "F", True)                    # same image: moves to F, no duplicate
    assert mgr.startup_entries() == [{"image": os.path.abspath(b), "letter": "F"}]


def test_disabling_other_image_keeps_letter_entry(env):
    mgr, _, _, image = env
    a, b = image("a.img"), image("b.img")
    mgr.set_startup(a, "E", True)
    mgr.set_startup(b, "E", False)                   # b was never flagged: a must stay
    assert mgr.is_startup_image(a)


def test_invalid_entries_are_ignored(env):
    mgr, _, _, _ = env
    mgr.config.set("startup_mounts", [{"image": "x.img"}, "junk", {"image": "y.img", "letter": "EE"},
                                      {"image": "z.img", "letter": "g:"}])
    assert mgr.startup_entries() == [{"image": "z.img", "letter": "G"}]


def test_startup_mount_uses_wanted_letter(env):
    mgr, backend, _, image = env
    mgr.set_startup(image("a.img"), "E", True)
    results = mgr.mount_startup_images()
    assert backend.mounted == [("a.img", "E")]
    assert results[0].record.letter == "E" and not results[0].moved


def test_startup_mount_falls_back_when_letter_taken(env):
    mgr, backend, used, image = env
    used.update({"A", "E"})                          # A: and E: already exist (not ours)
    mgr.set_startup(image("a.img"), "E", True)
    result = mgr.mount_startup_images()[0]
    assert result.record.letter == "B" and result.moved
    assert mgr.startup_entries()[0]["letter"] == "E"  # preference is kept for next time


def test_missing_image_reported_and_entry_kept(env):
    mgr, backend, _, _ = env
    mgr.set_startup("C:\\nowhere\\gone.img", "E", True)
    result = mgr.mount_startup_images()[0]
    assert result.record is None and result.error is not None
    assert backend.mounted == []
    assert len(mgr.startup_entries()) == 1


def test_already_mounted_image_is_skipped(env):
    mgr, backend, _, image = env
    a = image("a.img")
    mgr.set_startup(a, "E", True)
    mgr.mount(a, "E")                                # e.g. still mounted after an elevated restart
    backend.mounted.clear()
    assert mgr.mount_startup_images() == []
    assert backend.mounted == []
