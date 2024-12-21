import logging.config
import os
from pathlib import Path

import yaml


def configure_logging() -> None:
    with (Path(__file__).parent.parent / "logging_config.yaml").open() as f:
        logging_config = yaml.safe_load(f)

    app_log_level = os.getenv("APP_LOG_LEVEL", "INFO").upper()
    external_log_level = os.getenv("EXTERNAL_LOG_LEVEL", "WARNING").upper()

    if "root" in logging_config["loggers"]:
        logging_config["loggers"]["root"]["level"] = app_log_level
    if "third_party" in logging_config["loggers"]:
        logging_config["loggers"]["third_party"]["level"] = external_log_level

    logging.config.dictConfig(logging_config)

    for logger_name in logging.root.manager.loggerDict:
        if not logger_name.startswith("__main__") and not logger_name.startswith("src"):
            logging.getLogger(logger_name).setLevel(external_log_level)
