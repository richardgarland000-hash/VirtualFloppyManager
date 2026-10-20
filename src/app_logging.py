"""Rotating file logger."""

import logging
import logging.handlers
import sys
import threading

from paths import log_path

ROOT_NAME = "floppymounter"


def setup_logging(level="INFO"):
    logger = logging.getLogger(ROOT_NAME)
    logger.setLevel(getattr(logging, str(level).upper(), logging.INFO))
    if not logger.handlers:
        fmt = logging.Formatter("%(asctime)s %(levelname)-7s %(name)s: %(message)s")
        try:
            fh = logging.handlers.RotatingFileHandler(
                log_path(), maxBytes=512 * 1024, backupCount=3, encoding="utf-8")
            fh.setFormatter(fmt)
            logger.addHandler(fh)
        except OSError:
            pass
        if sys.stderr is not None:
            sh = logging.StreamHandler()
            sh.setFormatter(fmt)
            logger.addHandler(sh)

        def _excepthook(exc_type, exc, tb):
            logger.critical("Unhandled exception", exc_info=(exc_type, exc, tb))

        sys.excepthook = _excepthook
        threading.excepthook = lambda a: logger.critical(
            "Unhandled thread exception", exc_info=(a.exc_type, a.exc_value, a.exc_traceback))
    return logger


def set_level(level):
    logging.getLogger(ROOT_NAME).setLevel(getattr(logging, str(level).upper(), logging.INFO))
