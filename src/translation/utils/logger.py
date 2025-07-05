import logging
from config import get_settings

def get_logger(name: str):
    settings = get_settings()
    logger = logging.getLogger(name)

    if not logger.handlers:
        handler = logging.StreamHandler()
        formatter = logging.Formatter(
            "%(asctime)s — %(name)s — %(levelname)s — %(message)s"
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)

        # Dynamically set log level based on .env
        level = settings.LOG_LEVEL.upper()
        logger.setLevel(getattr(logging, level, logging.INFO))

    return logger
