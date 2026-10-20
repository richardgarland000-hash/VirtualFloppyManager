"""Build driver.  Usage:  python build.py [--onedir]

Produces in dist/:
  FloppyMounter.exe                         (or dist/FloppyMounter/ with --onedir)
  FloppyMounter-<version>-win64.zip         exe + README + LICENSE + startup-task script
  SHA256SUMS.txt
"""

import hashlib
import os
import shutil
import subprocess
import sys
import zipfile

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(ROOT, "src"))
from constants import VERSION  # noqa: E402

DIST = os.path.join(ROOT, "dist")
BUILD = os.path.join(ROOT, "build")


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main():
    onedir = "--onedir" in sys.argv
    env = dict(os.environ, FM_ONEDIR="1" if onedir else "0")
    shutil.rmtree(DIST, ignore_errors=True)
    subprocess.check_call(
        [sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean",
         "--distpath", DIST, "--workpath", os.path.join(BUILD, "work"),
         os.path.join(ROOT, "packaging", "FloppyMounter.spec")], cwd=ROOT, env=env)

    extras = [os.path.join(ROOT, "README.md"), os.path.join(ROOT, "LICENSE"),
              os.path.join(ROOT, "packaging", "startup-task.ps1")]
    suffix = "-onedir" if onedir else ""
    zip_path = os.path.join(DIST, f"FloppyMounter-{VERSION}-win64{suffix}.zip")
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        if onedir:
            base = os.path.join(DIST, "FloppyMounter")
            for folder, _, files in os.walk(base):
                for name in files:
                    full = os.path.join(folder, name)
                    zf.write(full, os.path.join("FloppyMounter", os.path.relpath(full, base)))
        else:
            zf.write(os.path.join(DIST, "FloppyMounter.exe"), "FloppyMounter.exe")
        for extra in extras:
            if os.path.isfile(extra):
                zf.write(extra, os.path.basename(extra))

    sums = [zip_path] if onedir else [os.path.join(DIST, "FloppyMounter.exe"), zip_path]
    with open(os.path.join(DIST, "SHA256SUMS.txt"), "w") as fh:
        for path in sums:
            fh.write(f"{sha256(path)}  {os.path.basename(path)}\n")
    print("\nBuilt:", *[os.path.basename(p) for p in sums], sep="\n  ")


if __name__ == "__main__":
    main()
