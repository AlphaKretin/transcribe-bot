import logging
import os
from logging.handlers import TimedRotatingFileHandler


def setup_logging():
    """Log to the console and to a file in LOG_DIR that rolls over at midnight."""
    log_dir = os.getenv("LOG_DIR") or "logs"
    retention_days = int(os.getenv("LOG_RETENTION_DAYS") or 30)
    os.makedirs(log_dir, exist_ok=True)

    formatter = logging.Formatter(
        "%(asctime)s %(levelname)-8s %(name)s: %(message)s", "%Y-%m-%d %H:%M:%S"
    )
    console_handler = logging.StreamHandler()
    file_handler = TimedRotatingFileHandler(
        os.path.join(log_dir, "bot.log"),
        when="midnight",
        backupCount=retention_days,
        encoding="utf-8",
    )
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    for handler in (console_handler, file_handler):
        handler.setFormatter(formatter)
        root.addHandler(handler)
    logging.captureWarnings(True)


def describe_request(message, user):
    """Who asked for what and where, for log lines."""
    if message.guild:
        where = f"{message.guild.name} #{message.channel.name}"
    else:
        where = "DMs"
    return f"user {user} ({user.id}) in {where}, message {message.jump_url}"
