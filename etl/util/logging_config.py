"""
    Shared logger setup for every listener/service/task in this project.
    Author: Nabeel Ahmed Jamil
"""
import sys
import logging
import colorlog

LOG_COLORS = {
    "DEBUG": "cyan",
    "INFO": "white",
    "WARNING": "yellow",
    "ERROR": "red",
    "CRITICAL": "red,bg_white",
}

LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"


def get_logger(name: str, level: int = logging.INFO) -> logging.Logger:
    """Colored output when attached to a real terminal, plain text otherwise. `docker logs`
    (and any redirected/piped destination) is never a tty, so without this check every level --
    INFO most of all, mapped to white -- printed raw ANSI escape codes there instead of color,
    which either shows as literal "\x1b[37m" junk or, in a viewer that does interpret them,
    invisible white-on-white text."""
    handler = colorlog.StreamHandler()
    if sys.stderr.isatty():
        handler.setFormatter(colorlog.ColoredFormatter("%(log_color)s" + LOG_FORMAT, log_colors=LOG_COLORS))
    else:
        handler.setFormatter(logging.Formatter(LOG_FORMAT))
    logger = colorlog.getLogger(name)
    logger.addHandler(handler)
    logger.setLevel(level)
    return logger
