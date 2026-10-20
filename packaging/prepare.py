"""Generate build-time resources: the .ico and the Windows version resource."""

import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SRC = os.path.join(ROOT, "src")
sys.path.insert(0, SRC)


def ensure_icon(force=False):
    path = os.path.join(ROOT, "assets", "floppy.ico")
    if force or not os.path.isfile(path):
        from icon_art import make_floppy
        os.makedirs(os.path.dirname(path), exist_ok=True)
        make_floppy(256).save(path, format="ICO",
                              sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    return path


def write_version_info():
    from constants import APP_TITLE, VERSION
    parts = (VERSION.split(".") + ["0", "0", "0"])[:4]
    nums = ", ".join(str(int(p)) for p in parts)
    text = f"""VSVersionInfo(
  ffi=FixedFileInfo(filevers=({nums}), prodvers=({nums}), mask=0x3f, flags=0x0,
                    OS=0x40004, fileType=0x1, subtype=0x0, date=(0, 0)),
  kids=[
    StringFileInfo([StringTable('040904B0', [
      StringStruct('FileDescription', '{APP_TITLE}'),
      StringStruct('FileVersion', '{VERSION}'),
      StringStruct('InternalName', 'FloppyMounter'),
      StringStruct('OriginalFilename', 'FloppyMounter.exe'),
      StringStruct('ProductName', '{APP_TITLE}'),
      StringStruct('ProductVersion', '{VERSION}'),
    ])]),
    VarFileInfo([VarStruct('Translation', [1033, 1200])])
  ]
)
"""
    out_dir = os.path.join(ROOT, "build")
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, "version_info.txt")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)
    return path


if __name__ == "__main__":
    print(ensure_icon(force=True))
    print(write_version_info())
