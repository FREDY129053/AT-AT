import logging
from shared.logging import configure_logging

configure_logging("api_agent", log_file="./all_logs.log", file_mode='w')

logging.getLogger('httpx').setLevel(logging.WARNING)
logger = logging.getLogger(__name__)