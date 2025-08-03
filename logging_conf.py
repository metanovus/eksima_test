import os
import sys
import logging
from logging.handlers import RotatingFileHandler

service_type = os.environ.get('SERVICE_TYPE', 'default')
log_dir = f"logs/{service_type}" if service_type != 'default' else "logs"
os.makedirs(log_dir, exist_ok=True)

rotating_handler = RotatingFileHandler(
    os.path.join(log_dir, f"{service_type}.log"),
    encoding="utf-8",
    maxBytes=10 * 1024 * 1024,
    backupCount=10
)

console_handler = logging.StreamHandler(sys.stdout)
console_handler.setLevel(logging.INFO)
console_handler.setFormatter(logging.Formatter(f"[{service_type.upper()}] %(asctime)s [%(levelname)s] %(message)s"))
console_handler.stream = open(sys.stdout.fileno(), mode='w', encoding='utf-8', buffering=1)

logging.basicConfig(
    level=logging.INFO,
    format=f"[{service_type.upper()}] %(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        rotating_handler,
        console_handler
    ]
)

logger = logging.getLogger(__name__)
