import logging
import sys
from typing import Literal

#############################
####   COLORED  OUTPUT   ####
#############################
try:
    import colorama
    from colorama import Fore, Style
    from colorama import init as colorama_init

    colorama_init(autoreset=True)
    COLORAMA_AVAILABLE = True
except ImportError:
    COLORAMA_AVAILABLE = False


#############################
####    CUSTOM FILTER    ####
#############################
class ServiceFilter(logging.Filter):
    def __init__(self, name: str):
        super().__init__()
        self.service_name = name

    def filter(self, record: logging.LogRecord) -> bool:
        record.service_name = self.service_name
        return True


#############################
####  CUSTOM FORMATTER   ####
#############################
class ColoredFormatter(logging.Formatter):
    COLOR_MAP = {
        logging.DEBUG: Fore.CYAN if COLORAMA_AVAILABLE else "",  # type: ignore
        logging.INFO: Fore.GREEN if COLORAMA_AVAILABLE else "",  # type: ignore
        logging.WARNING: Fore.YELLOW if COLORAMA_AVAILABLE else "",  # type: ignore
        logging.ERROR: Fore.RED if COLORAMA_AVAILABLE else "",  # type: ignore
        logging.CRITICAL: Fore.MAGENTA + Style.BRIGHT if COLORAMA_AVAILABLE else "",  # type: ignore
    }

    LEVEL_SHORT = {
        logging.DEBUG: "D",
        logging.INFO: "I",
        logging.WARNING: "W",
        logging.ERROR: "E",
        logging.CRITICAL: "C",
    }

    def format(self, record: logging.LogRecord) -> str:
        if COLORAMA_AVAILABLE:
            level_color = self.COLOR_MAP.get(record.levelno, "")
            original_level_name = record.levelname

            record.levelname = f"{level_color}{self.LEVEL_SHORT.get(record.levelno, '?')}{Style.RESET_ALL}"  # type: ignore
            result = super().format(record)
            record.levelname = original_level_name

            return result
        else:
            return super().format(record)


def configure_logging(
    service_name: str,
    level: int = logging.INFO,
    log_file: str | None = None,
    file_mode: Literal['a', 'w'] = 'a',
    colored_console: bool = True,
):
    log_format = (
        "%(asctime)s %(levelname)s %(name)s service=%(service_name)s %(message)s"
    )
    date_format = "%H:%M:%S"

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.addFilter(ServiceFilter(service_name))
    if colored_console and COLORAMA_AVAILABLE:
        console_formatter = ColoredFormatter(log_format, datefmt=date_format)
    else:
        console_formatter = logging.Formatter(log_format, datefmt=date_format)
    console_handler.setFormatter(console_formatter)

    root = logging.getLogger()
    root.handlers.clear()
    root.setLevel(level)
    root.addHandler(console_handler)

    if log_file:
        file_handler = logging.FileHandler(log_file, mode=file_mode)
        file_handler.addFilter(ServiceFilter(service_name))
        file_handler.setFormatter(
            logging.Formatter(
                "%(asctime)s %(levelname)s %(name)s service=%(service_name)s %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
        )
        root.addHandler(file_handler)
