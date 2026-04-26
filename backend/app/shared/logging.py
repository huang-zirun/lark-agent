import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path


class StructuredFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        base = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        for key in ("run_id", "stage_key", "provider_id", "model"):
            value = getattr(record, key, None)
            if value is not None:
                base[key] = value

        if record.exc_info and record.exc_info[1]:
            base["exception"] = str(record.exc_info[1])

        return json.dumps(base, ensure_ascii=False)


class ContextLoggerAdapter(logging.LoggerAdapter):
    def process(self, msg, kwargs):
        extra = kwargs.get("extra", {})
        extra.update(self.extra)
        kwargs["extra"] = extra
        return msg, kwargs


def setup_logging(debug: bool = True):
    level = logging.DEBUG if debug else logging.INFO

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(StructuredFormatter())
    console_handler.setLevel(level)

    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    root_logger.handlers.clear()
    root_logger.addHandler(console_handler)

    try:
        from app.shared.config import settings
        log_dir = Path(settings.LOG_DIR)
        log_dir.mkdir(parents=True, exist_ok=True)

        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        file_handler = logging.FileHandler(
            str(log_dir / f"devflow-{today}.log"),
            encoding="utf-8",
        )
        file_handler.setFormatter(StructuredFormatter())
        file_handler.setLevel(level)
        root_logger.addHandler(file_handler)
    except Exception:
        pass


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)


def get_context_logger(name: str, **context) -> ContextLoggerAdapter:
    logger = logging.getLogger(name)
    return ContextLoggerAdapter(logger, extra=context)


def sanitize_for_logging(text: str, max_length: int = 200) -> str:
    if len(text) > max_length:
        return text[:max_length] + "..."
    return text


def mask_api_key(key: str) -> str:
    if not key or len(key) < 8:
        return "***"
    return key[:4] + "***" + key[-4:]
