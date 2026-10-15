import os

import discord
from pydub import AudioSegment

from bot.replies import report_error


async def send_mp3(message, replied_message, user):
    """Post the voice message that `message` transcribes, converted to MP3."""
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
