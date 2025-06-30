# utm/log_config.py

import logging
import logging.config

def setup_logging(
    level_console: str = "INFO",
) -> None:
    """
    Configure root logger to write INFO+ messages (or higher) to stdout only.
    """
    config: dict = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "standard": {
                "format": "%(asctime)s %(name)s %(levelname)s %(message)s",
            },
        },
        "handlers": {
            "console_handler": {
                "class": "logging.StreamHandler",
                "level": level_console,
                "formatter": "standard",
                "stream": "ext://sys.stdout",
            },
        },
        "root": {
            "handlers": ["console_handler"],
            "level": "DEBUG",
            "propagate": False,
        },
    }
    logging.config.dictConfig(config)
