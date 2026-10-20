import pytest

from config import Config
from mount_manager import ImageError, MountManager, MountRecord


class NoBackend:
    """Any call means the guard failed: replace must be rejected before touching the drive."""
    def __getattr__(self, name):
        raise AssertionError(f"backend.{name} should not be called")


@pytest.fixture
def setup(tmp_path):
    img = tmp_path / "disk.img"
    img.write_bytes(bytes(1474560))                 # blank 1.44 MB image is mountable
    other = tmp_path / "other.img"
    other.write_bytes(bytes(1474560))
    mgr = MountManager(Config(str(tmp_path / "c.json")), NoBackend())
    mgr._records = [MountRecord("Z", str(img), "Blank", False, "")]
    return mgr, str(img), str(other)


def test_is_same_image(setup):
    mgr, img, other = setup
    assert mgr.is_same_image("Z", img)
    assert mgr.is_same_image("Z:", f'"{img}"')      # drive colon and quotes tolerated
    assert not mgr.is_same_image("Z", other)
    assert not mgr.is_same_image("Y", img)          # nothing mounted on Y


def test_replace_with_same_image_rejected_before_unmount(setup):
    mgr, img, _ = setup
    with pytest.raises(ImageError, match="already mounted"):
        mgr.replace("Z", img)
