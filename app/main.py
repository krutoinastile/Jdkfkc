import asyncio
import logging
import sys
import time

from app.config import get_settings
from app.logging_config import setup_logging
from app.runtime import run_bot

logger = logging.getLogger(__name__)

MAX_RESTART_BACKOFF = 60


def main() -> None:
    settings = get_settings()
    setup_logging(settings.log_level)

    backoff = 5
    while True:
        try:
            asyncio.run(run_bot(settings))
            logger.warning("Polling stopped — restarting in %ss", backoff)
        except KeyboardInterrupt:
            logger.info("Shutdown requested")
            sys.exit(0)
        except Exception:
            logger.exception("Bot crashed — restarting in %ss", backoff)

        time.sleep(backoff)
        backoff = min(backoff * 2, MAX_RESTART_BACKOFF)


if __name__ == "__main__":
    main()
