# Changelog

## 1.2.1
- Exit dialog: new "Unmount all except startup images, then exit" option (shown when the mounted images are a mix of startup and non-startup ones); startup images are marked in the list and stay mounted

## 1.2.0
- "Mount at startup" option in the Mount section: flagged images are mounted automatically when the program starts, shown in a new "At startup" column, toggled from the right-click menu, and managed under Settings > Mounted at startup
- If a startup image's drive letter is taken, the next free letter is used; missing images are reported (balloon notification when hidden in the tray) and kept in the list
- Drag and drop an image file onto the image box or the info panel (works while running as administrator)

## 1.1.0
- Colored interface: blue header band with a mounted-count badge, themed controls, color-coded buttons (green Mount, red Unmount, amber Replace), striped mounted list with read-only rows marked
- Image info panel is color-coded: green border for a clean image, amber with highlighted warnings, red for errors
- Status bar message color shows success, warning or error
- Layout fixes: bottom button bar and Unmount button can no longer be squeezed or clipped

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
