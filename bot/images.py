import logging
import os
import re
import time
from io import BytesIO

import discord
import requests
from PIL import Image, ImageOps

from bot import models
from bot.config import MOONDREAM_FLAG
from bot.replies import reply_deletable, report_error

log = logging.getLogger(__name__)


SPOILER_SPAN = re.compile(r"\|\|(.+?)\|\|", re.DOTALL)


def is_spoiler_embed(embed, content):
    """Whether embed's link sits inside a ||spoiler|| span of the message text."""
    url = embed.url or embed.image.url or embed.thumbnail.url
    return bool(url) and any(url in span for span in SPOILER_SPAN.findall(content))


async def invert_image(image, message, reactor, spoiler):
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
                file=discord.File(f"inverted_image_{message_id}.png", spoiler=spoiler),
                allowed_mentions=discord.AllowedMentions(users=False),
            )
        except discord.HTTPException:
            new_message = await message.channel.send(
                f"{message.author.mention} {reactor.mention}",
                file=discord.File(f"inverted_image_{message_id}.png", spoiler=spoiler),
                allowed_mentions=discord.AllowedMentions(users=False),
            )
        await new_message.add_reaction("🗑️")
    finally:
        os.remove(f"inverted_image_{message_id}.png")


async def caption_image(image, message, reactor, spoiler):
    if models.moondream_model is None:
        await reply_deletable(
            message,
            reactor,
            "Sorry, image descriptions are not available right now. "
            "The Moondream model was not loaded when the bot started. "
            f"Please ask the bot administrator to restart with the `{MOONDREAM_FLAG}` flag to enable this feature.",
        )
        return

    start_time = time.time()  # Start measuring time
    caption = models.moondream_model.caption(image, length="normal")
    end_time = time.time()  # Stop measuring time
    elapsed_time = end_time - start_time
    text = caption["caption"]
    if spoiler:
        text = f"||{text}||"
    new_message = await message.reply(
        f"{reactor.mention} {text}",
        allowed_mentions=discord.AllowedMentions(users=False),
    )
    await new_message.add_reaction("🗑️")
    log.info("Captioning time: %.2fs", elapsed_time)


async def process_images(message, user, emoji_name):
    """Invert or describe every image in message's embeds and attachments."""
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
                await process_image(
                    image, message, user, is_spoiler_embed(embed, message.content)
                )
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
                await process_image(image, message, user, attachment.is_spoiler())
        except Exception:
            await report_error(action, message, user)
        finally:
            # Delete the images
            if os.path.exists(attachment.filename):
                os.remove(attachment.filename)
