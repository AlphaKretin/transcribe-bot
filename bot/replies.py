import logging
import secrets

import discord

from bot.logs import describe_request

log = logging.getLogger(__name__)


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
