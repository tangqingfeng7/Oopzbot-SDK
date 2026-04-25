from __future__ import annotations

import logging
import sys


SDK_LOGGER_NAME = "oopz_sdk"


def setup_logging(level: int | str = "INFO") -> None:
    logger = logging.getLogger(SDK_LOGGER_NAME)

    if isinstance(level, str):
        level = logging._nameToLevel.get(level.upper(), logging.INFO)

    logger.handlers.clear()
    logger.setLevel(level)
    logger.propagate = False

    handler = logging.StreamHandler(sys.stderr)
    handler.setLevel(level)
    handler.setFormatter(
        logging.Formatter(
            "[%(asctime)s] [%(levelname)s] %(name)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    )

    logger.addHandler(handler)