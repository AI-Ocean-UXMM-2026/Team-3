import logging
import re


class HideQueryString(logging.Filter):
    def filter(self, record):
        # Uvicorn's request line is its third positional argument. Search terms may
        # be customer names/phones; no query strings should reach access logs.
        if isinstance(record.args, tuple) and len(record.args) == 5:
            args = list(record.args)
            if isinstance(args[2], str):
                args[2] = args[2].split("?", 1)[0]
                args[2] = re.sub(r"(/(?:api/)?confirm/)[^/ ]+", r"\1[REDACTED]", args[2])
                record.args = tuple(args)
        return True


def install_access_filter():
    logger = logging.getLogger("uvicorn.access")
    if not any(isinstance(item, HideQueryString) for item in logger.filters):
        logger.addFilter(HideQueryString())
