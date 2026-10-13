import contextvars
import json
import logging
from datetime import UTC, datetime
from typing import Any

request_id_context: contextvars.ContextVar[str] = contextvars.ContextVar(
    "request_id", default=""
)


class JsonFormatter(logging.Formatter):
    """Emit compact structured logs without request bodies or credential fields."""

    def format(self, record: logging.LogRecord) -> str:
        event: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        request_id = request_id_context.get()
        if request_id:
            event["request_id"] = request_id
        if record.exc_info:
            exception_type = record.exc_info[0]
            if exception_type is not None:
                event["exception_type"] = exception_type.__name__
        return json.dumps(event, separators=(",", ":"), ensure_ascii=True)
