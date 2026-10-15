import logging
import os
import time

import discord

from bot import models
from bot.config import DISCORD_CHAR_LIMIT, PROJECT_DIR
from bot.replies import chunk_text, report_error

log = logging.getLogger(__name__)


async def transcribe_voice_messages(message):
    for attachment in message.attachments:
        if attachment.filename != "voice-message.ogg":
            continue
        # add message id to file name
        file_name = os.path.join(PROJECT_DIR, f"{message.id}-{attachment.filename}")
        try:
            # save the file
            await attachment.save(file_name)
            log.info("Saved attachment: %s", file_name)

            start_time = time.time()  # Start measuring time

            segments, _ = models.whisper_model.transcribe(file_name)
            transcribed_text = "".join(segment.text for segment in segments).strip()

            end_time = time.time()  # Stop measuring time
            elapsed_time = end_time - start_time

            if message.guild:
                server_nickname = message.author.display_name
                prefix = f"**{server_nickname}**: "
                fallback_prefix = f"**{server_nickname}** ({message.author.mention}): "
            else:
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
                    allowed_mentions=discord.AllowedMentions(replied_user=False),
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
