import logging

def setup_logger(name: str) -> logging.Logger:
    """Sets up a standardized logger for the production bot."""
    logging.basicConfig(
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        level=logging.INFO
    )
    return logging.getLogger(name)

logger = setup_logger(__name__)
