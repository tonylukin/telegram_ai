import logging
from logging.handlers import RotatingFileHandler
import os
from app.config import is_prod

LOG_DIR = "logs"
LOG_FILE = "fastapi.log"

handlers = [logging.StreamHandler()]
if is_prod():
    os.makedirs(LOG_DIR, exist_ok=True)
    handlers.append(RotatingFileHandler(os.path.join(LOG_DIR, LOG_FILE), maxBytes=10_000_000, backupCount=5))

log_level = logging.ERROR if is_prod() else logging.INFO
logging.basicConfig(
    level=log_level,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=handlers
)

logger = logging.getLogger(__name__)
