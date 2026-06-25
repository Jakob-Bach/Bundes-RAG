import logging

from bundesrag.config import Settings

LOGGER_NAME = "bundesrag"


def setup_logging(settings: Settings) -> logging.Logger:
    """Configures the package logger to write to settings.log_file.

    Re-pointing is idempotent: a call with the same log_file as the current
    handler is a no-op, but a different log_file (e.g. a fresh tmp_path per
    test) replaces the handler instead of leaking one per call."""
    logger = logging.getLogger(LOGGER_NAME)
    if getattr(logger, "_bundesrag_log_file", None) == settings.log_file:
        return logger

    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
        handler.close()

    settings.log_file.parent.mkdir(parents=True, exist_ok=True)
    handler = logging.FileHandler(settings.log_file, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False
    logger._bundesrag_log_file = settings.log_file
    return logger
