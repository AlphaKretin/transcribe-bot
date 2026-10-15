import argparse
import logging
import os
import secrets
import time
from io import BytesIO
from logging.handlers import TimedRotatingFileHandler

import discord
import requests
import whisper
from dotenv import load_dotenv
from PIL import Image, ImageOps
from pydub import AudioSegment

# Parse command-line arguments
MOONDREAM_FLAG = "--moondream"
parser = argparse.ArgumentParser(description="Discord transcription bot")
parser.add_argument(
    MOONDREAM_FLAG,
    action="store_true",
    help="Enable the Moondream model for image descriptions",
)
args = parser.parse_args()

# This assumes a .env file with this name has been placed in the same file location that the program is running from.
load_dotenv("bot_params.env")


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
        os.path.join(log_dir, "necho.log"),
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


setup_logging()
log = logging.getLogger("necho")

model_size = os.getenv("MODEL_SIZE") or "base"

model = whisper.load_model(model_size)

log.info("Loaded Whisper using model size: %s", model_size)

moondream_model = None
if args.moondream:
    from transformers import AutoModelForCausalLM

    moondream_model = AutoModelForCausalLM.from_pretrained(
        "vikhyatk/moondream2",
        revision="2025-06-21",
        trust_remote_code=True,
        # Comment/uncomment to control use of GPU for Moondream
        device_map={"": "cuda"},
    )
    log.info("Loaded Moondream")
else:
    log.info("Moondream model disabled (use %s to enable)", MOONDREAM_FLAG)


DISCORD_CHAR_LIMIT = 2000


def chunk_text(text, first_limit, rest_limit):
    """Split text at word boundaries. First chunk uses first_limit, the rest use rest_limit."""

    def split_once(t, limit):
        if len(t) <= limit:
            return t, ""
        split_at = t.rfind(" ", 0, limit)
        if split_at <= 0:
            split_at = limit
        return t[:split_at], t[split_at:].lstrip()

    chunks = []
    chunk, remaining = split_once(text, first_limit)
    chunks.append(chunk)
    while remaining:
        chunk, remaining = split_once(remaining, rest_limit)
        chunks.append(chunk)
    return chunks


def describe_request(message, user):
    """Who asked for what and where, for log lines."""
    if message.guild:
        where = f"{message.guild.name} #{message.channel.name}"
    else:
        where = "DMs"
    return f"user {user} ({user.id}) in {where}, message {message.jump_url}"


async def reply_deletable(message, requester, text):
    """Reply to message with a silent mention of requester, so they can remove it with 🗑️."""
    content = f"{requester.mention} {text}"
    try:
        new_message = await message.reply(
            content,
            allowed_mentions=discord.AllowedMentions(users=False),
        )
    except discord.HTTPException:
        # Original message was deleted, send without reply
        if requester != message.author:
            content = f"{message.author.mention} {content}"
        new_message = await message.channel.send(
            content,
            allowed_mentions=discord.AllowedMentions(users=False),
        )
    await new_message.add_reaction("🗑️")


async def report_error(action, message, requester):
    """Log the exception being handled, and tell the requester that `action` failed.

    Must be called from an except block.
    """
    error_id = secrets.token_hex(3)
    log.exception(
        "Failed to %s [error ID %s] for %s",
        action,
        error_id,
        describe_request(message, requester),
    )
    try:
        await reply_deletable(
            message,
            requester,
            f"Sorry, there was an error and I couldn't {action}. :(\n"
            f"Please let the admin know, quoting error ID `{error_id}`.",
        )
    except Exception:
        log.exception("Could not post the message for error ID %s", error_id)


class MyClient(discord.Client):
    async def on_ready(self):
        log.info("Logged on as %s", self.user)

    async def on_error(self, event_method, *args, **kwargs):
        details = []
        for arg in args:
            if isinstance(arg, discord.Message):
                details.append(describe_request(arg, arg.author))
            elif isinstance(arg, discord.RawReactionActionEvent):
                details.append(
                    f"reaction {arg.emoji} by user {arg.user_id} "
                    f"on message {arg.message_id} in channel {arg.channel_id}"
                )
        log.exception(
            "Unhandled error in %s (%s)",
            event_method,
            "; ".join(details) or "no details",
        )

    async def on_message(self, message):
        # don't respond to ourselves, other bots, or webhooks
        if message.author == self.user or message.author.bot or message.webhook_id:
            return

        if message.attachments:
            for attachment in message.attachments:
                if attachment.filename == "voice-message.ogg":
                    file_name = attachment.filename
                    # add message id to file name
                    file_name = f"{message.id}-{file_name}"
                    try:
                        # save the file
                        await attachment.save(file_name)
                        log.info("Saved attachment: %s", file_name)

                        start_time = time.time()  # Start measuring time

                        text = whisper.transcribe(model, file_name)
                        transcribed_text = text["text"].strip()

                        end_time = time.time()  # Stop measuring time
                        elapsed_time = end_time - start_time

                        # get the user's nickname
                        if message.guild:
                            server_nickname = message.guild.get_member(
                                message.author.id
                            ).display_name
                            prefix = f"**{server_nickname}**: "
                            fallback_prefix = (
                                f"**{server_nickname}** ({message.author.mention}): "
                            )
                        else:
                            server_nickname = None
                            prefix = ""
                            fallback_prefix = f"{message.author.mention}: "

                        text_chunks = chunk_text(
                            transcribed_text,
                            first_limit=DISCORD_CHAR_LIMIT - len(prefix),
                            rest_limit=DISCORD_CHAR_LIMIT,
                        )

                        try:
                            new_message = await message.reply(prefix + text_chunks[0])
                        except discord.HTTPException:
                            # Original message was deleted, send without reply
                            new_message = await message.channel.send(
                                fallback_prefix + text_chunks[0],
                            )
                        await new_message.add_reaction("🗑️")
                        await new_message.add_reaction("⬇️")

                        # Send continuation chunks as replies to the first message;
                        # 🗑️ on the first message will find and delete these via history scan
                        for chunk in text_chunks[1:]:
                            await message.channel.send(
                                chunk,
                                reference=new_message,
                                allowed_mentions=discord.AllowedMentions(
                                    replied_user=False
                                ),
                            )

                        log.info("Transcription time: %.2fs", elapsed_time)

                    except Exception:
                        await report_error(
                            "transcribe this voice message", message, message.author
                        )
                    finally:
                        # delete the file
                        if os.path.exists(file_name):
                            os.remove(file_name)


intents = discord.Intents.default()
intents.message_content = True
# guilds is required to get the nickname of the user
intents.members = True

client = MyClient(intents=intents)

TRIGGER_EMOJI = ["invert_image", "image_desc"]


async def invert_image(image, message, reactor):
    if image.mode == "RGBA":
        r, g, b, a = image.split()
        image = Image.merge("RGB", (r, g, b))
    inverted_image = ImageOps.invert(image)
    message_id = message.id
    inverted_image.save(f"inverted_image_{message_id}.png")
    try:
        try:
            new_message = await message.reply(
                reactor.mention,
                file=discord.File(f"inverted_image_{message_id}.png"),
                allowed_mentions=discord.AllowedMentions(users=False),
            )
        except discord.HTTPException:
            new_message = await message.channel.send(
                f"{message.author.mention} {reactor.mention}",
                file=discord.File(f"inverted_image_{message_id}.png"),
                allowed_mentions=discord.AllowedMentions(users=False),
            )
        await new_message.add_reaction("🗑️")
    finally:
        os.remove(f"inverted_image_{message_id}.png")


async def caption_image(image, message, reactor):
    if moondream_model is None:
        await reply_deletable(
            message,
            reactor,
            "Sorry, image descriptions are not available right now. "
            "The Moondream model was not loaded when the bot started. "
            f"Please ask the bot administrator to restart with the `{MOONDREAM_FLAG}` flag to enable this feature.",
        )
        return

    start_time = time.time()  # Start measuring time
    caption = moondream_model.caption(image, length="normal")
    end_time = time.time()  # Stop measuring time
    elapsed_time = end_time - start_time
    new_message = await message.reply(
        f"{reactor.mention} {caption['caption']}",
        allowed_mentions=discord.AllowedMentions(users=False),
    )
    await new_message.add_reaction("🗑️")
    log.info("Captioning time: %.2fs", elapsed_time)


# This function is called when a reaction is added to a message.
# Added feature by Kvysteran: method was changed to overload on_raw_reaction_add instead of on_reacton_add.
# Before this change, every time the bot started or restarted, it would lose the ability to respond to
# any reactions added to messages that were posted before the latest restart.
@client.event
async def on_raw_reaction_add(payload):
    message = await client.get_channel(payload.channel_id).fetch_message(
        payload.message_id
    )
    user = payload.member
    emoji_name = str(payload.emoji)
    """
    We want to delete the message if
     - The user reacts with the garbage can emoji
     - The message was sent by the bot
     - The message the bot is replying to is owned by the user who reacted or an admin
    """
    if any(name in emoji_name for name in TRIGGER_EMOJI):
        if "invert_image" in emoji_name:
            process_image, action = invert_image, "invert this image"
        else:
            process_image, action = caption_image, "describe this image"

        # Added feature by Kvysteran: Loop through the embeds and try to download the images.
        # Before this change, posts would sometimes appear to contain an image but were unable to be
        # processed because the image was a displayed embed from a pasted link and not an attachment.
        for embed in message.embeds:
            link = embed.image.proxy_url or embed.thumbnail.proxy_url
            if link is None:
                await reply_deletable(
                    message,
                    user,
                    "Uh-oh, it looks like this message has an embedded link but no actual attached images.",
                )
                continue
            try:
                response = requests.get(link, timeout=30)
                response.raise_for_status()
                with Image.open(BytesIO(response.content)) as image:
                    await process_image(image, message, user)
            except Exception:
                await report_error(action, message, user)

        # Loop through the attachments
        for attachment in message.attachments:
            # Check if the attachment is an image
            if not (attachment.content_type or "").startswith("image"):
                continue
            try:
                # Download the image
                await attachment.save(attachment.filename)
                # Read the image
                with Image.open(attachment.filename) as image:
                    await process_image(image, message, user)
            except Exception:
                await report_error(action, message, user)
            finally:
                # Delete the images
                if os.path.exists(attachment.filename):
                    os.remove(attachment.filename)

    # Check if the user is the bot
    if user == client.user:
        return

    # Check if the message was sent by the bot
    if message.author != client.user:
        return

    # Check if the message is a reply
    if message.reference:
        # Get the message the bot is replying to
        replied_message = await message.channel.fetch_message(
            message.reference.message_id
        )
    else:
        replied_message = None

    # Check if the reaction is the garbage can emoji
    if str(payload.emoji) == "🗑️":
        # Check if user has permission to delete
        has_permission = False
        if replied_message and replied_message.author == user:
            # User owns the message that was replied to
            has_permission = True
        elif user in message.mentions:
            # User is mentioned in the message (fallback for when original was deleted)
            has_permission = True

        if has_permission:
            async for hist_msg in message.channel.history(limit=50, after=message):
                if (
                    hist_msg.author == client.user
                    and hist_msg.reference
                    and hist_msg.reference.message_id == message.id
                ):
                    await hist_msg.delete()
            await message.delete()

    # Check if the reaction is the download emoji
    if str(payload.emoji) == "⬇️":
        # Check if the message is a reply
        if not replied_message:
            return
        # Check the reply is owned by the user who reacted
        if replied_message.author != user:
            return

        # The only way we get here is if
        # - The reaction is the download emoji
        # - The message is a reply
        # - The replied message is owned by the user who reacted

        # This means we can download the file and send it back to the user

        # Download the file
        # Get the first attachment
        attachment = replied_message.attachments[0]
        filenameMP3 = attachment.filename.replace(".ogg", ".mp3")
        try:
            # Save the file
            await attachment.save(attachment.filename)
            audioMP3 = AudioSegment.from_ogg(attachment.filename)
            # Added feature by Kvysteran: convert the .ogg file to .mp3 before making the file available for download.
            # This makes playback of saved voice recordings easier for people that use Apple devices.
            # REQUIRED: the ffprobe executable must be placed in the same file location that this python program is running from.
            # If you have ffmpeg.exe but not ffprobe.exe, this conversion will fail and cause a crash.  :(
            audioMP3.export(filenameMP3, format="mp3")
            # Send the file
            await message.channel.send(file=discord.File(filenameMP3))
        except Exception:
            await report_error("convert this voice message", message, user)
        finally:
            # Delete the files
            for file_name in (attachment.filename, filenameMP3):
                if os.path.exists(file_name):
                    os.remove(file_name)


client.run(os.getenv("BOT_TOKEN"), log_handler=None)
