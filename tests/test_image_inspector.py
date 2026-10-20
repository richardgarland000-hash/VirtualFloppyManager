import struct

from image_inspector import inspect_image


def fat12_144(label=b"TESTDISK   "):
    b = bytearray(1474560)
    b[0:3] = b"\xEB\x3C\x90"
    b[3:11] = b"MSDOS5.0"
    struct.pack_into("<HBHBHHBHHH", b, 11, 512, 1, 1, 2, 224, 2880, 0xF0, 9, 18, 2)
    b[38] = 0x29
    b[43:54] = label
    b[54:62] = b"FAT12   "
    b[510:512] = b"\x55\xaa"
    return b


def write(tmp_path, name, data):
    p = tmp_path / name
    p.write_bytes(bytes(data))
    return str(p)


def test_fat12_detected(tmp_path):
    info = inspect_image(write(tmp_path, "a.img", fat12_144()))
    assert info.filesystem == "FAT12"
    assert info.label == "TESTDISK"
    assert info.pc_floppy and info.mountable
    assert "1.44 MB" in info.size_label


def test_blank_image(tmp_path):
    info = inspect_image(write(tmp_path, "b.img", bytes(737280)))
    assert info.filesystem.startswith("Blank")
    assert info.mountable


def test_imd_is_not_mountable(tmp_path):
    info = inspect_image(write(tmp_path, "c.imd", b"IMD 1.18: 01/01/2000" + bytes(2000)))
    assert not info.mountable
    assert "IMD" in info.container


def test_amiga_adf(tmp_path):
    data = bytearray(901120)
    data[0:4] = b"DOS\x01"
    info = inspect_image(write(tmp_path, "d.adf", data))
    assert info.filesystem == "Amiga FFS"


def test_tiny_file_rejected(tmp_path):
    info = inspect_image(write(tmp_path, "e.img", b"x" * 100))
    assert not info.mountable
