# Changelog

## 1.0.3
- Replace is disabled (button and right-click menu) and rejected when the selected image is already the one mounted on that drive

## 1.0.2
- Right-click menu on the mounted images list (Unmount, Replace with the selected image)

## 1.0.1
- Fix: "Access is denied" on unmount while already elevated was reported as a missing-privilege error. It now means the drive is busy, retries once, then offers a forced unmount

## 1.0.0
- Tray utility to mount/unmount raw floppy images as drive letters via ImDisk
- Image structure detection (FAT12/16/32, Amiga, HFS/MFS, MBR, IMD/TD0/HFE/VHD containers)
- Mount history (last 10), replace-image workflow, forced unmount of untracked ImDisk drives
- Automatic UAC elevation; packaged build requires administrator at launch
- PyInstaller packaging, optional logon scheduled task, GitHub Actions build and release
