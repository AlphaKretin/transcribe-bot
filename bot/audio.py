import os

import av
import discord

from bot.replies import report_error


def ogg_to_mp3(source, destination):
    with av.open(source) as input_file, av.open(destination, "w") as output_file:
        input_stream = input_file.streams.audio[0]
        output_stream = output_file.add_stream("libmp3lame", rate=input_stream.rate)
        output_stream.layout = input_stream.layout
        resampler = av.AudioResampler(
            format=output_stream.format,
            layout=output_stream.layout,
            rate=output_stream.rate,
        )
        for frame in input_file.decode(input_stream):
            for resampled in resampler.resample(frame):
                output_file.mux(output_stream.encode(resampled))
        for resampled in resampler.resample(None):
            output_file.mux(output_stream.encode(resampled))
        output_file.mux(output_stream.encode(None))


async def send_mp3(message, replied_message, user):
    """Post the voice message that `message` transcribes, converted to MP3."""
    # Get the first attachment
    attachment = replied_message.attachments[0]
    filenameMP3 = attachment.filename.replace(".ogg", ".mp3")
    try:
        # Save the file
        await attachment.save(attachment.filename)
        # Added feature by Kvysteran: convert the .ogg file to .mp3 before making the file available for download.
        # This makes playback of saved voice recordings easier for people that use Apple devices.
        ogg_to_mp3(attachment.filename, filenameMP3)
        # Send the file
        await message.channel.send(file=discord.File(filenameMP3))
    except Exception:
        await report_error("convert this voice message", message, user)
    finally:
        # Delete the files
        for file_name in (attachment.filename, filenameMP3):
            if os.path.exists(file_name):
                os.remove(file_name)
