import logging
import socket
import sys
import threading
from datetime import datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path
import structlog
from dateutil.tz import tzlocal
LOCAL_TZ=tzlocal()

class EventRenamer(object):  # with a better name hopefully
    def __init__(self, field_name):
        self._field_name = field_name

    def __call__(self, logger, name, event_dict):
        if 'event' in event_dict and not isinstance(event_dict['event'], dict):
            event_dict[self._field_name] = event_dict.pop('event')
        return event_dict

def add_thread_info(logger, method_name, event_dict):  # pylint: disable=unused-argument
    thread = threading.current_thread()
    event_dict['thread_id'] = thread.ident
    event_dict['thread_name'] = thread.name
    event_dict['source_host'] = socket.gethostname()
    return event_dict

def add_local_timestamp(logger, method_name, event_dict):
    now = datetime.now(LOCAL_TZ)
    event_dict['@timestamp'] = now.isoformat(timespec = 'milliseconds')
    return event_dict

def add_upper_log_level(logger, method_name, event_dict):
    """
    Add the log level to the event dict.
    """
    event_dict["level"] = method_name.upper()
    return event_dict

def configure_logger(log_name, log_dir, log_level):
    eventrenamer = EventRenamer("message")

    shared_processors = [
        structlog.stdlib.add_logger_name,
        add_upper_log_level,
        add_thread_info,
        add_local_timestamp,
        eventrenamer
    ]
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            add_upper_log_level,
            add_thread_info,
            structlog.stdlib.PositionalArgumentsFormatter(),
            add_local_timestamp,
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            structlog.stdlib.render_to_log_kwargs,
            #eventrenamer
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    formatter = structlog.stdlib.ProcessorFormatter(
        processor=structlog.processors.JSONRenderer(),
        foreign_pre_chain=shared_processors,
    )

    if log_dir:
        log_dir = Path(log_dir)
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file = log_dir / ("%s.json.log" % log_name)
        handler = RotatingFileHandler(log_file, maxBytes=10 * 1024 * 1024, backupCount=5)
    else:
        handler = logging.StreamHandler(sys.stdout)

    handler.setFormatter(formatter)
    root_logger = logging.getLogger()
    root_logger.addHandler(handler)
    root_logger.setLevel(log_level)

    logger = structlog.get_logger(log_name)
    logger.setLevel(log_level)
    return logger
