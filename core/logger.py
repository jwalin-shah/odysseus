import json
import logging
import os


def get_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)

    if not logger.handlers:
        handler = logging.StreamHandler()
        formatter = logging.Formatter('%(asctime)s %(name)s %(levelname)s %(message)s')
        handler.setFormatter(formatter)
        logger.addHandler(handler)

    log_level = os.environ.get('LOG_LEVEL', '').upper()
    if log_level in ('DEBUG', 'INFO', 'WARNING', 'ERROR'):
        logger.setLevel(getattr(logging, log_level))

    return logger


def structured_log(logger, level, msg, **kwargs):
    payload = {msg: msg, **kwargs}
    logger.log(level, json.dumps(payload))