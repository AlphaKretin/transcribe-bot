import os

from dotenv import load_dotenv

from bot import client, config, models
from bot.logs import setup_logging


def main():
    args = config.parse_args()
    # This assumes a .env file with this name has been placed in the same file location that the program is running from.
    load_dotenv("bot_params.env")
    setup_logging()
    models.load(os.getenv("MODEL_SIZE") or "base", args.moondream)
    client.run(os.getenv("BOT_TOKEN"))


if __name__ == "__main__":
    main()
