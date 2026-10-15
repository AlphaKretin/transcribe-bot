import logging
import os
import time

import discord
import whisper

from bot import models
from bot.config import DISCORD_CHAR_LIMIT
from bot.replies import chunk_text, report_error

log = logging.getLogger(__name__)


async def transcribe_voice_messages(message):
    for attachment in message.attachments:
        if attachment.filename != "voice-message.ogg":
            continue
        # add message id to file name
        file_name = f"{message.id}-{attachment.filename}"
        try:
            # save the file
            await attachment.save(file_name)
            log.info("Saved attachment: %s", file_name)

            start_time = time.time()  # Start measuring time

            text = whisper.transcribe(models.whisper_model, file_name)
            transcribed_text = text["text"].strip()

            end_time = time.time()  # Stop measuring time
            elapsed_time = end_time - start_time

            # get the user's nickname
            if message.guild:
                server_nickname = message.guild.get_member(
                    message.author.id
                ).display_name
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
