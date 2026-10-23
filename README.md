# Floppy Image Mounter Version 1.2.0

A Windows system-tray utility that mounts raw floppy disk images (`.img`, `.ima`, `.flp`, `.vfd`, `.dsk`, `.xdf`, ...) as drive letters, detects the disk's filesystem structure, and keeps track of what is mounted where.

This project utilizes the [ImDisk Toolkit](https://sourceforge.net/projects/imdisk-toolkit/) open-source project and adds additional features to simplify floppy image management. Although ImDisk supports more than just floppy images, this application is focused solely on floppy images. **Note:** The AIM Toolkit that supersedes ImDisk does not support floppy images.

## What's new
- Flag images to mount at app startup
- New drag and drop feature for selecting an image to mount

## Features
- Colored, color-coded interface (header badge, green/amber/red image check, status colors)
- Tray icon with tooltip listing mounted images; right-click menu to open the window, open settings, unmount an image, or quit
- Browse dialog, drag and drop onto the image box, and history of the last 10 mounted images
- "Mount at startup": flagged images are mounted automatically whenever the program starts
- Manage mounted images in a simple list
- Image structure detection: FAT12/16/32 geometry and label, Amiga, HFS/MFS, MBR, and recognition of non-raw containers (IMD, TD0, HFE, VHD) with an in-depth description
- Image files that can't be mounted are reported with meaningful errors
- Only free drive letters offered, in alphabetical order
- Unmount, or **replace** a mounted image with another in one step, useful when working with multi-disk image sets
- Warning, with optional forced unmount, when a letter is already taken by an untracked ImDisk drive (real drives are never touched)
- All slow work runs on worker threads with a progress dialog; state is re-checked periodically and after every operation
- Exit prompt when images are still mounted (unmount all / exit immediately / cancel)
- Settings, history and mount records in a JSON file; rotating log file
- The application runs as a portable app, extract the files in the zip file to a directory and run it from there

## Requirements
- Windows 10/11, 64-bit
- [ImDisk Toolkit](https://sourceforge.net/projects/imdisk-toolkit/) installed. It is a separate project and is **not bundled**. Windows cannot attach raw floppy images natively (`Mount-DiskImage` only handles ISO/VHD/VHDX), so this app drives `imdisk.exe`.
- Administrator rights. The packaged exe requests them at every launch via its manifest. When run from source, the app relaunches itself through UAC.

## Download
Grab `FloppyMounter.exe` (or the zip) from the **Releases** page. Verify against `SHA256SUMS.txt`. The exe is unsigned, so SmartScreen may warn on first run.

## Mount at startup
Tick **Mount at startup** in the Mount section before clicking Mount (or right-click an image in the list > *Mount at startup*). The list shows a **Yes** in the *At startup* column. On the next start the program remounts those images on their saved letters. If a letter is taken it uses the next free one and tells you; if an image file is missing you are told and the entry is kept. Remove entries under **Settings > Mounted at startup**. Quitting with "Unmount all and exit" keeps the startup list.

## Drag and drop
Drop an image file onto the image box (or the info panel under it) to select it. Because the program runs as administrator, Windows normally blocks drops from a non-elevated Explorer window. The program opens the window-message filter for the shell's drop messages to allow it. If a drop is refused on your system, use Browse instead.

## Run from source
```
pip install -r requirements.txt
python src/main.py
```

## Build the executable
```
build.bat                 # creates .venv, installs deps, builds dist\FloppyMounter.exe
build.bat --onedir        # folder build: faster start-up, better for installers
```
or manually: `pip install -r requirements.txt -r requirements-dev.txt` then `python build.py`.

Output in `dist/`: `FloppyMounter.exe`, `FloppyMounter-<version>-win64.zip`, `SHA256SUMS.txt`.
The icon and Windows version resource are generated at build time from `src/icon_art.py` and `src/constants.py`.
The spec file `packaging/FloppyMounter.spec` sets `uac_admin=True`, which embeds `requireAdministrator` in the exe.

## Start elevated at logon
A program that requires administrator rights cannot start from the Startup folder without a UAC prompt. Register a scheduled task that runs with highest privileges, from an elevated PowerShell:
```
.\startup-task.ps1                    # starts hidden in the tray at logon
.\startup-task.ps1 -Visible           # show the window at logon
.\startup-task.ps1 -Remove            # uninstall
```
The script is also in the release zip. Command-line flags: `--hidden` (start in tray), `--no-elevate` (source runs only).

## Files and locations
Config (`floppy_mounter.json`), log (`floppy_mounter.log`) and a generated icon are stored next to the program. If that folder is not writable they go to `%LOCALAPPDATA%\FloppyMounter`. Put your own icon at `assets\floppy.ico` beside the exe to override the built-in one.

## Project layout
```
src/            application code (see module docstrings)
packaging/      PyInstaller spec, build resources, startup-task script
tests/          pytest suite (image inspector, config)
build.py        build driver
build.bat       one-step local build
.github/        CI: test, build, and publish on tags
```

## Releasing
1. Update `VERSION` in `src/constants.py` and `CHANGELOG.md`
2. `git tag vX.Y.Z && git push --tags`. The workflow tests, builds and attaches the files to a GitHub Release (it fails if the tag and `VERSION` disagree).

## Troubleshooting
- **"ImDisk was not found"**: install ImDisk Toolkit or set the path to `imdisk.exe` in Settings.
- **Windows asks to format the drive after mounting**: the image has no filesystem Windows understands (blank, Amiga, HFS...). Click Cancel; the structure panel warns about this beforehand.
- **Unmount says the drive is in use**: close Explorer windows or programs using it, or accept the forced unmount.
- Check `floppy_mounter.log` for the exact ImDisk commands and output.

## License
MIT. See `LICENSE`.
