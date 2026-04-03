import logging
import os
from tqdm import tqdm

# Create the logs folder if it does not exist
os.makedirs("logs", exist_ok=True)

class TqdmLoggingHandler(logging.Handler):
    """
    Instead of using print(), use tqdm.write().
    """
    def __init__(self, level=logging.NOTSET):
        super().__init__(level)

    def emit(self, record):
        try:
            msg = self.format(record)
            tqdm.write(msg)
            self.flush()
        except Exception:
            self.handleError(record)

def setup_logger(name="forensic_pipeline"):
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)  # Capture EVERYTHING

    # Avoid duplicates if called multiple times
    if logger.hasHandlers():
        return logger

    # 1. FILE HANDLER (Writes everything to a file, including debug details)
    file_handler = logging.FileHandler("logs/pipeline.log", mode='a', encoding='utf-8')
    file_handler.setLevel(logging.DEBUG)
    file_formatter = logging.Formatter('%(asctime)s - %(levelname)s - [%(filename)s] - %(message)s')
    file_handler.setFormatter(file_formatter)

    # 2. CONSOLE HANDLER (Writes INFO/ERROR to the screen via TQDM)
    console_handler = TqdmLoggingHandler(level=logging.INFO)
    console_formatter = logging.Formatter('CMD: %(message)s') # Short format for the console
    console_handler.setFormatter(console_formatter)

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    return logger

# Global instance
log = setup_logger()