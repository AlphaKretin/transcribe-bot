import logging

import discord

from bot.audio import send_mp3
from bot.config import TRIGGER_EMOJI
from bot.images import process_images
from bot.logs import describe_request
from bot.transcription import transcribe_voice_messages

log = logging.getLogger(__name__)


class BotClient(discord.Client):
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

        await transcribe_voice_messages(message)

    # Added feature by Kvysteran: method was changed to overload on_raw_reaction_add instead of on_reacton_add.
    # Before this change, every time the bot started or restarted, it would lose the ability to respond to
    # any reactions added to messages that were posted before the latest restart.
    async def on_raw_reaction_add(self, payload):
        channel = self.get_channel(payload.channel_id) or await self.fetch_channel(
            payload.channel_id
        )
        if not isinstance(channel, discord.abc.Messageable):
            return
        message = await channel.fetch_message(payload.message_id)
        # payload.member is only set in servers
        user = (
            payload.member
            or self.get_user(payload.user_id)
            or await self.fetch_user(payload.user_id)
        )
        emoji_name = str(payload.emoji)

        if any(name in emoji_name for name in TRIGGER_EMOJI):
            await process_images(message, user, emoji_name)

        # Check if the user is the bot
        if user == self.user:
            return

        # Check if the message was sent by the bot
        if message.author != self.user:
            return

        # Check if the message is a reply
        if message.reference and message.reference.message_id:
            # Get the message the bot is replying to
            replied_message = await message.channel.fetch_message(
                message.reference.message_id
            )
        else:
            replied_message = None

        if emoji_name == "🗑️":
            await self.delete_if_permitted(message, replied_message, user)

        if emoji_name == "⬇️":
            # Only the author of the voice message can download it
            if replied_message and replied_message.author == user:
                await send_mp3(message, replied_message, user)

    async def delete_if_permitted(self, message, replied_message, user):
        """Delete a bot message, and the bot's replies to it, if user may remove it.

        Permitted if user wrote the message the bot replied to, or is mentioned in it
        (the fallback for when the original was deleted).
        """
        if not (
            (replied_message and replied_message.author == user)
            or user in message.mentions
        ):
            return

        async for hist_msg in message.channel.history(limit=50, after=message):
            if (
                hist_msg.author == self.user
                and hist_msg.reference
                and hist_msg.reference.message_id == message.id
            ):
                await hist_msg.delete()
        await message.delete()


def run(token):
    intents = discord.Intents.default()
    intents.message_content = True
    # guilds is required to get the nickname of the user
    intents.members = True

    # The bot never joins voice channels, so PyNaCl isn't needed; skip its startup warning.
    discord.VoiceClient.warn_nacl = False
    client = BotClient(intents=intents)
    client.run(token, log_handler=None)
