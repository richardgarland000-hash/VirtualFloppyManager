"""Application controller: wires GUI, tray, worker threads and the mount manager."""

import logging
import os
import queue
import sys
import threading
import tkinter as tk
from tkinter import messagebox

import app_logging
from config import Config
from constants import APP_TITLE, VERSION
from dialogs import ProgressDialog, QuitDialog
from drive_utils import available_letters, is_admin
from elevation import restart_elevated
from icons import Icons
from imdisk_backend import BackendError, ImDiskBackend
from main_window import MainWindow
from mount_manager import (ForeignDriveError, ImageError, MountManager,
                           has_allowed_extension)
from paths import config_path, log_path
from settings_dialog import SettingsDialog
from tray import TrayIcon

log = logging.getLogger("floppymounter.app")


class App:
    def __init__(self):
        self.config = Config(config_path())
        app_logging.setup_logging(self.config.get("log_level"))
        log.info("%s %s starting (admin=%s, log=%s)", APP_TITLE, VERSION, is_admin(), log_path())

        self.backend = ImDiskBackend(self.config)
        self.manager = MountManager(self.config, self.backend)
        self.busy = False
        self._quitting = False
        self._settings = None
        self._last_sig = None
        self.ui_queue = queue.Queue()

        self.root = tk.Tk()
        self.root.withdraw()
        self.icons = Icons()
        self.icons.apply(self.root)
        self.window = MainWindow(self.root, self)
        self.tray = TrayIcon(self)

    # ---- thread plumbing ---------------------------------------------
    def ui_call(self, fn):
        """Thread-safe: run fn on the Tk thread."""
        self.ui_queue.put(fn)

    def _pump(self):
        while True:
            try:
                fn = self.ui_queue.get_nowait()
            except queue.Empty:
                break
            try:
                fn()
            except Exception:
                log.exception("UI callback failed")
        if not self._quitting:
            self.root.after(100, self._pump)

    def run_task(self, title, func, on_success=None, on_error=None):
        """Run func(progress) on a worker thread behind a progress dialog."""
        if self.busy:
            self.root.bell()
            return
        self.busy = True
        self.window.update_states()
        dlg = ProgressDialog(self.root, title)

        def progress(msg):
            self.ui_call(lambda: dlg.set_message(msg))

        def finish(result, error):
            dlg.close()
            self.busy = False
            self.refresh_state()
            if error is not None:
                log.error("%s failed: %s", title, error)
                (on_error or (lambda e: self._report(e, title)))(error)
            elif on_success:
                on_success(result)

        def worker():
            try:
                result, error = func(progress), None
            except Exception as exc:
                result, error = None, exc
            self.ui_call(lambda: finish(result, error))

        threading.Thread(target=worker, daemon=True).start()

    # ---- startup / periodic ------------------------------------------
    def run(self):
        self.tray.start()
        self.root.after(100, self._pump)
        self.root.after(self._interval(), self._tick)
        threading.Thread(target=self._startup_reconcile, daemon=True).start()
        if not (self.config.get("start_hidden") or "--hidden" in sys.argv):
            self.show_window()
        if not is_admin():
            self.window.status("Not running as administrator - mounting may be refused.")
        self.refresh_state()
        self.root.mainloop()

    def _interval(self):
        return max(1, int(self.config.get("refresh_seconds"))) * 1000

    def _startup_reconcile(self):
        self.manager.reconcile(startup=True)
        self.ui_call(self.refresh_state)

    def _signature(self):
        return (tuple((r.letter, r.image) for r in self.manager.snapshot()), tuple(available_letters()))

    def _tick(self):
        if self._quitting:
            return
        if not self.busy:
            self.manager.reconcile()
            if self._signature() != self._last_sig:
                self.refresh_state()
        self.root.after(self._interval(), self._tick)

    def refresh_state(self):
        records = self.manager.snapshot()
        self._last_sig = self._signature()
        self.window.refresh(records)
        self.tray.update(records)

    # ---- window management -------------------------------------------
    def show_window(self):
        self.root.deiconify()
        self.root.state("normal")
        self.root.lift()
        self.root.focus_force()
        self.refresh_state()

    def hide_window(self):
        self.root.withdraw()

    def on_close_button(self):
        if self.config.get("close_button_hides"):
            self.hide_window()
        else:
            self.request_quit()

    def open_settings(self):
        if self._settings and self._settings.alive():
            self._settings.lift()
            return
        self._settings = SettingsDialog(self.root, self)

    def apply_settings(self):
        app_logging.set_level(self.config.get("log_level"))
        self.refresh_state()
        self.window.status("Settings saved.")

    # ---- error reporting ---------------------------------------------
    def _report(self, exc, title):
        if isinstance(exc, BackendError) and exc.kind == "not_found":
            if messagebox.askyesno(title, f"{exc}\n\nOpen Settings now?", parent=self.root):
                self.open_settings()
        elif isinstance(exc, (BackendError, ImageError, ForeignDriveError)):
            messagebox.showerror(title, str(exc), parent=self.root)
        else:
            log.exception("Unexpected error", exc_info=exc)
            messagebox.showerror(title, f"Unexpected error: {exc}\n\nSee the log file for details.",
                                 parent=self.root)

    # ---- mount / unmount / replace -----------------------------------
    def _extension_ok(self, image):
        allowed = self.config.get("allowed_extensions")
        if has_allowed_extension(image, allowed):
            return True
        return messagebox.askyesno(
            "Unusual file extension",
            f"'{os.path.splitext(image)[1] or '(none)'}' is not in your list of allowed extensions "
            f"({' '.join(allowed)}).\n\nTry to mount it anyway?", parent=self.root)

    def mount_image(self, image, letter, force_first=False):
        if not force_first and not self._extension_ok(image):
            return

        def work(progress):
            if force_first:
                self.manager.force_unmount_foreign(letter, progress)
            return self.manager.mount(image, letter, progress)

        self.run_task(f"Mounting on {letter}:", work, self._after_mount,
                      lambda e: self._mount_error(e, image, letter))

    def _after_mount(self, rec):
        self.window.status(f"Mounted {rec.name} on {rec.letter}:")
        if self.config.get("open_explorer_after_mount"):
            try:
                os.startfile(f"{rec.letter}:\\")
            except OSError as exc:
                log.warning("Could not open Explorer: %s", exc)

    def _mount_error(self, exc, image, letter):
        if isinstance(exc, ForeignDriveError):
            if exc.is_imdisk:
                if messagebox.askyesno(
                        "Drive already exists",
                        f"Drive {letter}: exists but is not in this application's list of mounted "
                        "images (it may have been mounted by another tool).\n\n"
                        "Force unmount it and mount the new image here? Open files on it may be lost.",
                        icon="warning", parent=self.root):
                    self.mount_image(image, letter, force_first=True)
            else:
                messagebox.showwarning(
                    "Drive already exists",
                    f"Drive {letter}: is in use by something that is not an ImDisk virtual disk "
                    "(for example a USB, network or hard drive). It will not be touched.\n\n"
                    "Choose another drive letter.", parent=self.root)
            self.refresh_state()
        else:
            self._report(exc, "Mount failed")

    def unmount_drive(self, letter, force=False):
        self.run_task(f"Unmounting {letter}:",
                      lambda p: self.manager.unmount(letter, force, p),
                      lambda _: self.window.status(f"Unmounted {letter}:"),
                      lambda e: self._unmount_error(e, letter, lambda: self.unmount_drive(letter, True)))

    def replace_drive(self, letter, image, force=False):
        if not force and not self._extension_ok(image):
            return
        rec = self.manager.get(letter)
        if not force and not messagebox.askyesno(
                "Replace image",
                f"Unmount {rec.name if rec else letter + ':'} from {letter}: and mount the new image there?",
                parent=self.root):
            return
        self.run_task(f"Replacing image on {letter}:",
                      lambda p: self.manager.replace(letter, image, force, p),
                      self._after_mount,
                      lambda e: self._unmount_error(e, letter, lambda: self.replace_drive(letter, image, True)))

    def _unmount_error(self, exc, letter, force_action):
        if isinstance(exc, BackendError) and exc.kind == "in_use":
            if messagebox.askyesno(
                    "Drive in use",
                    f"Drive {letter}: is in use. Close any Explorer windows or programs using it and "
                    "try again, or force the unmount (unsaved data on the disk may be lost).\n\n"
                    "Force unmount now?", icon="warning", parent=self.root):
                force_action()
        else:
            self._report(exc, "Unmount failed")

    def restart_as_admin(self):
        """Relaunch elevated (one UAC prompt). Mounted images stay mounted and are re-adopted."""
        if is_admin():
            messagebox.showinfo(APP_TITLE, "Already running as administrator.", parent=self.root)
            return
        if self.busy:
            messagebox.showinfo(APP_TITLE, "Please wait for the current operation to finish.", parent=self.root)
            return
        if not messagebox.askyesno(
                APP_TITLE, "Restart as administrator?\n\nMounted images stay mounted and will be "
                "picked up again by the new instance.", parent=self.root):
            return
        if restart_elevated():
            self._finish_quit()
        else:
            messagebox.showwarning(APP_TITLE, "The elevated restart was cancelled or failed.", parent=self.root)

    # ---- quit --------------------------------------------------------
    def request_quit(self):
        if self._quitting:
            return
        if self.busy:
            messagebox.showinfo(APP_TITLE, "An operation is in progress. Please wait for it to finish.",
                                parent=self.root)
            return
        records = self.manager.snapshot()
        if not records:
            self._finish_quit()
            return
        choice = QuitDialog(self.root, records).show()
        if choice == "unmount":
            self._unmount_all_and_quit(False)
        elif choice == "exit":
            self._finish_quit()

    def _unmount_all_and_quit(self, force):
        def done(failures):
            if not failures:
                self._finish_quit()
                return
            names = ", ".join(f"{letter}:" for letter, _ in failures)
            ans = messagebox.askyesnocancel(
                APP_TITLE,
                f"Could not unmount {names}.\n\nYes = force unmount\nNo = exit and leave them mounted\n"
                "Cancel = keep the application open", icon="warning", parent=self.root)
            if ans is True:
                self._unmount_all_and_quit(True)
            elif ans is False:
                self._finish_quit()

        self.run_task("Unmounting all images",
                      lambda p: self.manager.unmount_all(force, p), done)

    def _finish_quit(self):
        log.info("Shutting down")
        self._quitting = True
        self.tray.stop()
        self.root.destroy()
