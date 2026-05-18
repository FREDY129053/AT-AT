import logging

from shared.logging import configure_logging

configure_logging("ab_agent", log_file="./all_logs.log", file_mode="w")

logging.getLogger('httpx').setLevel(logging.WARNING)
logger = logging.getLogger(__name__)


def rabbit_temp(data: dict):
    import json
    with open("./temp/rabbit/env.txt", 'a') as file:
        file.write(json.dumps(data, indent=2))
        file.write("\n\n")

def ms_delta(timedelta) -> int:
    return (timedelta.total_seconds() * 1000)