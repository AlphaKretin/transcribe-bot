import os

from dotenv import load_dotenv

from bot import client, config, models
from bot.logs import setup_logging


def main():
    args = config.parse_args()
    load_dotenv(os.path.join(config.PROJECT_DIR, "bot_params.env"))
    setup_logging()
    models.load(os.getenv("MODEL_SIZE") or "small", args.moondream)
    client.run(os.getenv("BOT_TOKEN"))


if __name__ == "__main__":
    main()
