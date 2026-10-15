import logging
import re
import time
from functools import partial
from io import BytesIO

import discord
import requests
from PIL import Image, ImageOps

from bot import models
from bot.config import DISCORD_CHAR_LIMIT
from bot.replies import reply_deletable, report_error

log = logging.getLogger(__name__)

# Discord's limit on attachments per message
MAX_FILES = 10

SPOILER_SPAN = re.compile(r"\|\|(.+?)\|\|", re.DOTALL)


def is_spoiler_embed(embed, content):
    """Whether embed's link sits inside a ||spoiler|| span of the message text."""
    url = embed.url or embed.image.url or embed.thumbnail.url
    return bool(url) and any(url in span for span in SPOILER_SPAN.findall(content))


def invert_image(image):
    """Return image inverted, as PNG bytes."""
    if image.mode == "RGBA":
        r, g, b, a = image.split()
        image = Image.merge("RGB", (r, g, b))
    buffer = BytesIO()
    ImageOps.invert(image).save(buffer, "PNG")
    return buffer.getvalue()


def caption_image(model, image):
    start_time = time.time()
    caption = model.caption(image, length="normal")
    log.info("Captioning time: %.2fs", time.time() - start_time)
    return caption["caption"]


async def download(link):
    response = requests.get(link, timeout=30)
    response.raise_for_status()
    return response.content


async def post_output(message, reactor, anchor, text="", images=()):
    """Post text and (number, png, spoiler) images after a silent mention of reactor.

    The first post (anchor is None) replies to message and gets a 🗑️. Later posts reply
    to anchor, so that 🗑️ on it also removes them.
    """
    content = f"{reactor.mention} {text}".rstrip()
    mentions = discord.AllowedMentions(users=False)

    def send_kwargs():
        # a failed send closes its files, so each attempt needs new ones
        if not images:
            return {"allowed_mentions": mentions}
        files = [
            discord.File(BytesIO(png), f"inverted_image_{number}.png", spoiler=spoiler)
            for number, png, spoiler in images
        ]
        return {"files": files, "allowed_mentions": mentions}

    if anchor is not None:
        return await message.channel.send(content, reference=anchor, **send_kwargs())
    try:
        new_message = await message.reply(content, **send_kwargs())
    except discord.HTTPException as e:
        if e.status == 413:
            raise
        # Original message was deleted, send without reply
        if reactor != message.author:
            content = f"{message.author.mention} {content}"
        new_message = await message.channel.send(content, **send_kwargs())
    await new_message.add_reaction("🗑️")
    return new_message


async def post_images(message, reactor, results):
    anchor = None

    async def post(group):
        nonlocal anchor
        try:
            posted = await post_output(message, reactor, anchor, images=group)
        except discord.HTTPException as e:
            # Upload too large: retry as two smaller posts
            if e.status != 413 or len(group) == 1:
                raise
            half = len(group) // 2
            await post(group[:half])
            await post(group[half:])
            return
        anchor = anchor or posted

    for start in range(0, len(results), MAX_FILES):
        await post(results[start : start + MAX_FILES])


async def post_captions(message, reactor, results, numbered):
    lines = []
    for number, caption, spoiler in results:
        if spoiler:
            caption = f"||{caption}||"
        lines.append(f"{number}. {caption}" if numbered else caption)

    # room for both mentions, in case the fallback has to add the author's
    limit = DISCORD_CHAR_LIMIT - len(reactor.mention) - len(message.author.mention) - 2
    chunks = [lines[0]]
    for line in lines[1:]:
        if len(chunks[-1]) + 1 + len(line) > limit:
            chunks.append(line)
        else:
            chunks[-1] += "\n" + line

    anchor = None
    for chunk in chunks:
        posted = await post_output(message, reactor, anchor, text=chunk)
        anchor = anchor or posted


async def process_images(message, user, emoji_name):
    """Invert or describe every image in message's attachments and embeds, in one reply."""
    invert = "invert_image" in emoji_name
    action = "invert this image" if invert else "describe this image"

    # Each source is (read, spoiler), with read returning the image's bytes
    sources = []
    for attachment in message.attachments:
        if (attachment.content_type or "").startswith("image"):
            sources.append((attachment.read, attachment.is_spoiler()))
    # Added feature by Kvysteran: download images from embeds.
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
        sources.append(
            (partial(download, link), is_spoiler_embed(embed, message.content))
        )
    if not sources:
        return

    # Taken once, so turning Moondream off partway through doesn't break this request
    model = models.moondream_model
    if not invert and model is None:
        if models.moondream_loading:
            text = (
                "Image descriptions are being turned on right now. "
                "Please try again in a minute."
            )
        else:
            text = (
                "Sorry, image descriptions are not available right now. "
                "Please ask the bot owner to turn them on with `/moondream`."
            )
        await reply_deletable(message, user, text)
        return

    results = []
    for number, (read, spoiler) in enumerate(sources, 1):
        try:
            with Image.open(BytesIO(await read())) as image:
                if invert:
                    output = invert_image(image)
                else:
                    output = caption_image(model, image)
            results.append((number, output, spoiler))
        except Exception:
            await report_error(action, message, user)
    if not results:
        return

    try:
        if invert:
            await post_images(message, user, results)
        else:
            await post_captions(message, user, results, numbered=len(sources) > 1)
    except Exception:
        await report_error(action, message, user)
