import logging
from logging.handlers import RotatingFileHandler
import os

ENV = os.getenv("ENV", "dev")
LOG_DIR = "logs"
LOG_FILE = "fastapi.log"

if ENV == "prod":
    os.makedirs(LOG_DIR, exist_ok=True)

handlers = [logging.StreamHandler()]
if ENV == "prod":
    handlers.append(RotatingFileHandler(os.path.join(LOG_DIR, LOG_FILE), maxBytes=10_000_000, backupCount=5))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=handlers
)

logger = logging.getLogger(__name__)
