import argparse

MOONDREAM_FLAG = "--moondream"
DISCORD_CHAR_LIMIT = 2000
TRIGGER_EMOJI = ["invert_image", "image_desc"]


def parse_args():
    parser = argparse.ArgumentParser(description="Discord transcription bot")
    parser.add_argument(
        MOONDREAM_FLAG,
        action="store_true",
        help="Enable the Moondream model for image descriptions",
    )
    return parser.parse_args()
