"""System tray icon. pystray callbacks run on the tray thread, so they only
post work to the Tk thread via app.ui_call()."""

import logging

import pystray

from constants import APP_TITLE
from drive_utils import is_admin

log = logging.getLogger("floppymounter.tray")


class TrayIcon:
    def __init__(self, app):
        self.app = app
        self._active = None
        menu = pystray.Menu(
            pystray.MenuItem("Open window", self._open, default=True),
            pystray.MenuItem("Settings...", self._settings),
            pystray.MenuItem("Unmount image", pystray.Menu(self._unmount_items),
                             enabled=lambda item: bool(self.app.manager.snapshot())),
            pystray.MenuItem("Restart as administrator", self._restart_admin,
                             enabled=lambda item: not is_admin()),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Quit", self._quit),
        )
        self.icon = pystray.Icon("FloppyImageMounter", app.icons.tray(False), APP_TITLE, menu)

    def start(self):
        self.icon.run_detached()

    def stop(self):
        try:
            self.icon.stop()
        except Exception as exc:
            log.debug("Tray stop: %s", exc)

    # ---- menu --------------------------------------------------------
    def _unmount_items(self):
        records = self.app.manager.snapshot()
        if not records:
            yield pystray.MenuItem("(nothing mounted)", None, enabled=False)
            return
        for rec in records:
            yield pystray.MenuItem(f"{rec.letter}:  {rec.name}", self._make_unmount(rec.letter))

    def _make_unmount(self, letter):
        return lambda icon, item: self.app.ui_call(lambda: self.app.unmount_drive(letter))

    def _open(self, icon=None, item=None):
        self.app.ui_call(self.app.show_window)

    def _settings(self, icon=None, item=None):
        self.app.ui_call(self.app.open_settings)

    def _restart_admin(self, icon=None, item=None):
        self.app.ui_call(self.app.restart_as_admin)

    def _quit(self, icon=None, item=None):
        self.app.ui_call(self.app.request_quit)

    # ---- state -------------------------------------------------------
    def update(self, records):
        if records:
            title = APP_TITLE + "\n" + "\n".join(f"{r.letter}: {r.name}" for r in records)
        else:
            title = APP_TITLE + "\nNo images mounted"
        if len(title) > 127:                       # Windows tooltip limit
            title = title[:124] + "..."
        try:
            self.icon.title = title
            active = bool(records)
            if active != self._active:
                self._active = active
                self.icon.icon = self.app.icons.tray(active)
            self.icon.update_menu()
        except Exception as exc:
            log.debug("Tray update failed: %s", exc)
