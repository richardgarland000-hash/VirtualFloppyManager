"""Owns the list of mounted images and performs (blocking) mount operations.

All mount/unmount/replace/reconcile methods may block on external processes and
must be called from worker threads.
"""

import logging
import os
import threading
import time
from dataclasses import dataclass, asdict
from datetime import datetime

from drive_utils import available_letters, notify_shell, used_letters, wait_for_drive
from image_inspector import inspect_image
from imdisk_backend import BackendError

log = logging.getLogger("floppymounter.manager")


class ImageError(Exception):
    """The chosen image cannot be mounted."""


class ForeignDriveError(Exception):
    """The drive letter exists but is not one of our mounts."""

    def __init__(self, letter, is_imdisk):
        super().__init__(f"Drive {letter}: already exists but is not tracked by this application.")
        self.letter = letter
        self.is_imdisk = is_imdisk


@dataclass
class MountRecord:
    letter: str
    image: str
    fmt: str
    read_only: bool
    mounted_at: str

    @property
    def name(self):
        return os.path.basename(self.image)

    @classmethod
    def from_dict(cls, d):
        try:
            return cls(str(d["letter"]).upper(), str(d["image"]), str(d.get("fmt", "")),
                       bool(d.get("read_only", False)), str(d.get("mounted_at", "")))
        except (KeyError, TypeError):
            return None


@dataclass
class StartupResult:
    image: str
    wanted_letter: str
    record: "MountRecord" = None
    error: Exception = None

    @property
    def name(self):
        return os.path.basename(self.image)

    @property
    def moved(self):
        """Mounted, but on a different letter than the one that was requested."""
        return self.record is not None and self.record.letter != self.wanted_letter


def _norm(path):
    return os.path.normcase(os.path.abspath(path))


def has_allowed_extension(path, allowed):
    return os.path.splitext(path)[1].lower() in [e.lower() for e in allowed]


class MountManager:
    def __init__(self, config, backend):
        self.config = config
        self.backend = backend
        self._lock = threading.RLock()
        self._records = [r for r in (MountRecord.from_dict(d) for d in config.get("mounted")) if r]

    # ---- state -------------------------------------------------------
    def snapshot(self):
        with self._lock:
            return list(self._records)

    def get(self, letter):
        with self._lock:
            return next((r for r in self._records if r.letter == letter), None)

    def _persist(self):
        self.config.set("mounted", [asdict(r) for r in self._records])

    def _remove(self, letter):
        with self._lock:
            self._records = [r for r in self._records if r.letter != letter]
            self._persist()

    def _is_device(self, letter):
        try:
            return self.backend.is_device(letter)
        except BackendError:
            return False

    def is_same_image(self, letter, image):
        """True if `image` is the file already mounted on `letter`."""
        rec = self.get(letter.rstrip(":").upper())
        if not rec or not image.strip():
            return False
        candidate = os.path.abspath(os.path.expanduser(image.strip().strip('"')))
        return _norm(rec.image) == _norm(candidate)

    # ---- mount at startup ---------------------------------------------
    def startup_entries(self):
        """Valid entries of the 'mount at startup' list: [{"image", "letter"}]."""
        entries = []
        for e in self.config.get("startup_mounts"):
            if isinstance(e, dict) and isinstance(e.get("image"), str) \
                    and isinstance(e.get("letter"), str) and len(e["letter"].rstrip(":")) == 1:
                entries.append({"image": e["image"], "letter": e["letter"].rstrip(":").upper()})
        return entries

    def is_startup_image(self, image):
        norm = _norm(image)
        return any(_norm(e["image"]) == norm for e in self.startup_entries())

    def set_startup(self, image, letter, enabled):
        """Add (enabled) or remove (disabled) an image from the startup list. One entry per
        image and per drive letter, so a new entry replaces an older one for the same letter."""
        letter = letter.rstrip(":").upper()
        norm = _norm(image)
        with self._lock:
            entries = [e for e in self.startup_entries()
                       if _norm(e["image"]) != norm and not (enabled and e["letter"] == letter)]
            if enabled:
                entries.append({"image": os.path.abspath(image), "letter": letter})
            self.config.set("startup_mounts", sorted(entries, key=lambda e: e["letter"]))

    def mount_startup_images(self, progress=None):
        """Mount every image flagged for startup. Blocking; returns a StartupResult per image.

        Images that are already mounted (e.g. after an elevated restart) are skipped. If the
        wanted letter is taken, the first free letter is used instead. Missing or unreadable
        images are reported and their entries are kept."""
        progress = progress or (lambda m: None)
        results = []
        for entry in self.startup_entries():
            image, wanted = entry["image"], entry["letter"]
            result = StartupResult(image, wanted)
            try:
                if any(_norm(r.image) == _norm(image) for r in self.snapshot()):
                    continue
                letter = wanted
                if letter in used_letters():
                    free = available_letters()
                    if not free:
                        raise ImageError("No free drive letters are available.")
                    letter = free[0]
                    log.warning("Startup mount: %s: is taken, using %s: for %s", wanted, letter, image)
                progress(f"Mounting {result.name} on {letter}:...")
                result.record = self.mount(image, letter, progress)
            except Exception as exc:
                log.error("Startup mount of %s failed: %s", image, exc)
                result.error = exc
            results.append(result)
        return results

    # ---- validation --------------------------------------------------
    def validate_image(self, image, replacing=None):
        path = os.path.abspath(os.path.expanduser(image.strip().strip('"')))
        if not os.path.isfile(path):
            raise ImageError(f"File not found:\n{path}")
        try:
            with open(path, "rb") as fh:
                fh.read(512)
        except PermissionError:
            raise ImageError(f"Access denied reading the image:\n{path}")
        except OSError as exc:
            raise ImageError(f"Cannot read the image: {exc}")
        if os.path.getsize(path) == 0:
            raise ImageError("The image file is empty.")
        for rec in self.snapshot():
            if _norm(rec.image) == _norm(path) and rec.letter != replacing:
                raise ImageError(f"This image is already mounted on {rec.letter}:.")
        info = inspect_image(path)
        if not info.mountable:
            raise ImageError("\n".join([f"{info.container}: {info.filesystem}"] + info.warnings))
        return path, info

    # ---- operations --------------------------------------------------
    def mount(self, image, letter, progress=None):
        progress = progress or (lambda m: None)
        letter = letter.rstrip(":").upper()
        progress("Checking image...")
        path, info = self.validate_image(image)
        progress(f"Checking drive {letter}:...")
        if letter in used_letters():
            if self.get(letter):
                raise ImageError(f"Drive {letter}: already holds a mounted image.")
            raise ForeignDriveError(letter, self._is_device(letter))
        read_only = bool(self.config.get("read_only"))
        progress(f"Mounting on {letter}:...")
        self.backend.mount(path, letter, read_only,
                           bool(self.config.get("removable_media")), info.pc_floppy)
        progress("Verifying drive...")
        if not wait_for_drive(letter, True):
            try:
                self.backend.unmount(letter, True)
            except BackendError:
                pass
            raise BackendError(f"ImDisk reported success but drive {letter}: never appeared.")
        rec = MountRecord(letter, path, info.short(), read_only,
                          datetime.now().isoformat(timespec="seconds"))
        with self._lock:
            self._records = sorted(self._records + [rec], key=lambda r: r.letter)
            self._persist()
        self.config.add_history(path)
        notify_shell(letter, True)
        log.info("Mounted %s on %s:", path, letter)
        return rec

    def unmount(self, letter, force=False, progress=None):
        progress = progress or (lambda m: None)
        letter = letter.rstrip(":").upper()
        progress(f"Unmounting {letter}:...")
        if letter in used_letters():
            try:
                self.backend.unmount(letter, force)
            except BackendError as exc:
                if exc.kind != "in_use" or force:
                    raise
                progress(f"Drive {letter}: is busy, retrying...")   # handles often clear within a second
                time.sleep(1.5)
                self.backend.unmount(letter, False)
            if not wait_for_drive(letter, False):
                raise BackendError(f"Drive {letter}: is still present after unmounting.", "in_use")
        else:
            log.warning("Drive %s: was already gone", letter)
        self._remove(letter)
        notify_shell(letter, False)
        log.info("Unmounted %s:", letter)

    def replace(self, letter, image, force=False, progress=None):
        progress = progress or (lambda m: None)
        letter = letter.rstrip(":").upper()
        path, _ = self.validate_image(image, replacing=letter)   # fail before touching the old mount
        if self.is_same_image(letter, path):
            raise ImageError(f"That image is already mounted on {letter}:. Choose a different image.")
        self.unmount(letter, force, progress)
        try:
            return self.mount(image, letter, progress)
        except Exception as exc:
            raise BackendError(f"The old image was unmounted from {letter}:, "
                               f"but mounting the new one failed:\n\n{exc}") from exc

    def force_unmount_foreign(self, letter, progress=None):
        """Force-remove an ImDisk drive we have no record of. Never touches real drives."""
        progress = progress or (lambda m: None)
        letter = letter.rstrip(":").upper()
        if not self._is_device(letter):
            raise BackendError(f"Drive {letter}: is not an ImDisk virtual disk, so it will not be touched.")
        progress(f"Force unmounting {letter}:...")
        self.backend.unmount(letter, True)
        if not wait_for_drive(letter, False):
            raise BackendError(f"Drive {letter}: is still present after forced unmount.", "in_use")
        notify_shell(letter, False)

    def partition_by_startup(self):
        """(flagged, others): mounted records that are / are not flagged 'mount at startup'."""
        flagged, others = [], []
        for rec in self.snapshot():
            (flagged if self.is_startup_image(rec.image) else others).append(rec)
        return flagged, others

    def unmount_all(self, force=False, progress=None, letters=None):
        """Unmount every image, or only those whose drive letter is in `letters`."""
        failures = []
        for rec in self.snapshot():
            if letters is not None and rec.letter not in letters:
                continue
            try:
                self.unmount(rec.letter, force, progress)
            except Exception as exc:
                log.error("Could not unmount %s: %s", rec.letter, exc)
                failures.append((rec.letter, exc))
        return failures

    def reconcile(self, startup=False):
        """Drop records whose drive vanished (ejected externally, reboot...). Returns removed list."""
        used = used_letters()
        gone = []
        for rec in self.snapshot():
            if rec.letter not in used:
                gone.append(rec)
            elif startup:
                try:
                    if not self.backend.is_device(rec.letter):
                        gone.append(rec)     # letter reused by something else
                except BackendError:
                    pass                     # cannot verify; keep the record
        for rec in gone:
            log.warning("Drive %s: (%s) no longer mounted; removing record", rec.letter, rec.name)
            self._remove(rec.letter)
        return gone
