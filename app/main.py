import asyncio
import logging
import sys

from app.config import get_settings
from app.logging_config import setup_logging
from app.runtime import run_bot

logger = logging.getLogger(__name__)


def main() -> None:
    settings = get_settings()
    setup_logging(settings.log_level)
    try:
        asyncio.run(run_bot(settings))
    except KeyboardInterrupt:
        logger.info("Shutdown requested")
        sys.exit(0)


if __name__ == "__main__":
    main()
