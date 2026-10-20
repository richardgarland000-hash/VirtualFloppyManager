"""Detect the structure of a floppy disk image by reading its first sectors."""

import os
import struct
from dataclasses import dataclass, field

PC_FLOPPY_SIZES = {
    163840: '160 KB 5.25" SS/DD',
    184320: '180 KB 5.25" SS/DD',
    327680: '320 KB 5.25" DS/DD',
    368640: '360 KB 5.25" DS/DD',
    737280: '720 KB 3.5" DS/DD',
    1228800: '1.2 MB 5.25" DS/HD',
    1474560: '1.44 MB 3.5" DS/HD',
    1720320: '1.68 MB 3.5" DMF',
    2949120: '2.88 MB 3.5" DS/ED',
}
OTHER_FLOPPY_SIZES = {
    819200: '800 KB 3.5" DS/DD (Mac / Atari ST)',
    901120: '880 KB 3.5" DD (Amiga)',
    1802240: '1.76 MB 3.5" HD (Amiga)',
}
AMIGA_FLAGS = {0: "OFS", 1: "FFS", 2: "OFS international", 3: "FFS international",
               4: "OFS dir-cache", 5: "FFS dir-cache"}


@dataclass
class ImageInfo:
    path: str
    size: int
    size_label: str = ""
    pc_floppy: bool = False
    container: str = "Raw sector image"
    filesystem: str = "Unknown"
    label: str = ""
    details: list = field(default_factory=list)
    warnings: list = field(default_factory=list)
    mountable: bool = True

    def short(self):
        text = self.filesystem
        if self.size_label:
            text += f" ({self.size_label})"
        return text

    def summary(self):
        size_txt = f"{self.size:,} bytes"
        size_txt += f" - {self.size_label}" if self.size_label else " - non-standard floppy size"
        lines = [f"Size: {size_txt}", f"Container: {self.container}"]
        fs = self.filesystem + (f'  (label "{self.label}")' if self.label else "")
        lines.append(f"Structure: {fs}")
        lines.extend(self.details)
        lines.extend(f"Warning: {w}" for w in self.warnings)
        return "\n".join(lines)


def _u16(b, o):
    return struct.unpack_from("<H", b, o)[0]


def _u32(b, o):
    return struct.unpack_from("<I", b, o)[0]


def _text(raw):
    return raw.decode("cp437", errors="replace").strip(" \x00")


def _parse_fat(head, size, info):
    """Parse a FAT BIOS Parameter Block. Returns True if it looks valid."""
    if len(head) < 64:
        return False
    bps, spc, reserved, nfats = _u16(head, 11), head[13], _u16(head, 14), head[16]
    root_entries = _u16(head, 17)
    total = _u16(head, 19) or _u32(head, 32)
    media = head[21]
    fat_sectors = _u16(head, 22) or _u32(head, 36)
    spt, heads = _u16(head, 24), _u16(head, 26)

    if (bps not in (512, 1024, 2048, 4096) or spc == 0 or spc & (spc - 1)
            or reserved == 0 or nfats not in (1, 2) or total == 0
            or media < 0xF0 or fat_sectors == 0):
        return False

    root_sectors = (root_entries * 32 + bps - 1) // bps
    data_sectors = total - reserved - nfats * fat_sectors - root_sectors
    clusters = data_sectors // spc if data_sectors > 0 else 0
    if clusters < 4085:
        fat_type = "FAT12"
    elif clusters < 65525:
        fat_type = "FAT16"
    else:
        fat_type = "FAT32"

    info.filesystem = fat_type
    sig_off = 66 if fat_type == "FAT32" else 38
    if len(head) > sig_off + 25 and head[sig_off] in (0x28, 0x29):
        info.label = _text(head[sig_off + 5:sig_off + 16])
        if info.label.upper() == "NO NAME":
            info.label = ""
    oem = _text(head[3:11])
    if oem:
        info.details.append(f"OEM name: {oem}")
    info.details.append(
        f"Geometry: {bps} bytes/sector, {spc} sectors/cluster, {spt} sectors/track, "
        f"{heads} heads, media 0x{media:02X}")
    info.details.append(f"Volume: {total:,} sectors, {nfats} FAT(s) of {fat_sectors} sectors, "
                        f"{clusters:,} clusters")
    if total * bps > size:
        info.warnings.append("Image is smaller than its boot sector claims (truncated?).")
    if head[510:512] != b"\x55\xaa":
        info.warnings.append("Boot-sector signature 55AA missing (common on very old DOS disks).")
    return True


def inspect_image(path):
    """Read the file header and return an ImageInfo. Raises OSError if unreadable."""
    size = os.path.getsize(path)
    with open(path, "rb") as fh:
        head = fh.read(4096)
        fh.seek(0x8000)
        iso = fh.read(8)
        fh.seek(max(0, size - 512))
        tail = fh.read(512)

    info = ImageInfo(path=path, size=size)
    info.size_label = PC_FLOPPY_SIZES.get(size) or OTHER_FLOPPY_SIZES.get(size) or ""
    info.pc_floppy = size in PC_FLOPPY_SIZES
    ext = os.path.splitext(path)[1].lower()

    # Non-raw containers: detected, but cannot be mounted directly.
    container = None
    if head[:4] == b"IMD ":
        container = "ImageDisk (IMD)"
    elif head[:8] in (b"HXCPICFE", b"HXCHFEV3"):
        container = "HxC Floppy Emulator (HFE)"
    elif ext == ".td0" and head[:2] in (b"TD", b"td"):
        container = "Teledisk (TD0)"
    elif tail[:8] == b"conectix" or head[:8] == b"conectix":
        container = "Virtual PC / Hyper-V VHD"
    if container:
        info.container = container
        info.filesystem = "Not inspected (not a raw image)"
        info.mountable = False
        info.warnings.append("Not a raw sector image. Convert it to a raw .img first.")
        return info

    if size < 512:
        info.filesystem = "Too small to be a disk image"
        info.mountable = False
        return info

    if not any(head[:512]):
        info.filesystem = "Blank / unformatted"
        info.warnings.append("No filesystem found; Windows will offer to format the drive.")
    elif _parse_fat(head, size, info):
        pass
    elif head[:3] == b"DOS" and size in (901120, 1802240):
        info.filesystem = "Amiga " + AMIGA_FLAGS.get(head[3], f"DOS type {head[3]}")
        info.warnings.append("Windows cannot read Amiga filesystems; it will ask to format the drive.")
    elif head[1024:1026] == b"BD":
        info.filesystem = "Apple HFS"
        info.warnings.append("Windows cannot read HFS; it will ask to format the drive.")
    elif head[1024:1026] == b"\xd2\xd7":
        info.filesystem = "Apple MFS"
        info.warnings.append("Windows cannot read MFS; it will ask to format the drive.")
    elif iso[1:6] == b"CD001":
        info.filesystem = "ISO 9660 (optical disc)"
        info.warnings.append("This is a CD/DVD image, not a floppy.")
    elif head[510:512] == b"\x55\xaa" and any(head[450 + 16 * i] for i in range(4)):
        types = ", ".join(f"0x{head[450 + 16 * i]:02X}" for i in range(4) if head[450 + 16 * i])
        info.filesystem = "MBR-partitioned disk"
        info.details.append(f"Partition types: {types}")
        info.warnings.append("Partitioned image on removable media may not show its partitions.")
    else:
        info.filesystem = "Unrecognised"
        info.warnings.append("No known filesystem signature; Windows may ask to format the drive.")

    if not info.size_label:
        info.warnings.append("Size does not match a standard floppy format.")
    return info
