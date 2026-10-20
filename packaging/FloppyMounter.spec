# -*- mode: python ; coding: utf-8 -*-
# Build with:  python build.py          (single self-contained exe)
#              python build.py --onedir (folder build; faster start-up, better for installers)
import os
import sys

SPEC_DIR = SPECPATH                                   # provided by PyInstaller
ROOT = os.path.abspath(os.path.join(SPEC_DIR, ".."))
SRC = os.path.join(ROOT, "src")
sys.path.insert(0, SPEC_DIR)

import prepare                                        # noqa: E402

ICON = prepare.ensure_icon()
VERSION_FILE = prepare.write_version_info()
ONEDIR = os.environ.get("FM_ONEDIR") == "1"

a = Analysis(
    [os.path.join(SRC, "main.py")],
    pathex=[SRC],
    hiddenimports=["pystray._win32", "PIL._tkinter_finder"],
    excludes=["numpy", "pytest", "unittest", "pydoc"],
    noarchive=False,
)
pyz = PYZ(a.pure)

common = dict(
    name="FloppyMounter",
    icon=ICON,
    version=VERSION_FILE,
    console=False,
    uac_admin=True,        # embeds requestedExecutionLevel=requireAdministrator -> UAC prompt on every launch
    upx=False,             # UPX tends to trigger antivirus false positives
    disable_windowed_traceback=False,
)

if ONEDIR:
    exe = EXE(pyz, a.scripts, [], exclude_binaries=True, **common)
    coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name="FloppyMounter")
else:
    exe = EXE(pyz, a.scripts, a.binaries, a.datas, [], **common)
