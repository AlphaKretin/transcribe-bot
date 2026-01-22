import argparse
import os
import time
import traceback
from io import BytesIO
from sys import stderr

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

model_size = os.getenv("MODEL_SIZE") or "base"

model = whisper.load_model(model_size)

print("Loaded Whisper using Model Size:", model_size, file=stderr)

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
    print("Loaded Moondream", file=stderr)
else:
    print(f"Moondream model disabled (use {MOONDREAM_FLAG} to enable)", file=stderr)


class MyClient(discord.Client):
    async def on_ready(self):
        print(f"Logged on as {self.user}!")

    async def on_message(self, message):
        # don't respond to ourselves
        if message.author == self.user:
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
                        print(f"Saved attachment: {file_name}")

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
                            reply_message = f"**{server_nickname}**: {transcribed_text}"
                        else:
                            reply_message = transcribed_text

                        # We now want to add a garbage can emoji reaction to the bots message
                        # This will allow the user to delete the message if they want to

                        # We need to get the message that the bot just sent
                        new_message = await message.reply(reply_message)
                        # We need to add the garbage can emoji to the message
                        await new_message.add_reaction("🗑️")
                        await new_message.add_reaction("⬇️")

                        print(f"Transcription time: {elapsed_time:.2f}s", file=stderr)

                    except Exception as e:
                        traceback.print_exc()
                    finally:
                        # delete the file
                        os.remove(file_name)


intents = discord.Intents.default()
intents.message_content = True
# guilds is required to get the nickname of the user
intents.members = True

client = MyClient(intents=intents)

TRIGGER_EMOJI = ["invert_image", "image_desc"]


async def invert_image(image, message):
    # if the image is RGBA, convert it to RGB
    if image.mode == "RGBA":
        r, g, b, a = image.split()
        image = Image.merge("RGB", (r, g, b))
    # Invert the image
    inverted_image = ImageOps.invert(image)
    # Save the inverted image
    # Get message id
    message_id = message.id
    inverted_image.save(f"inverted_image_{message_id}.png")
    # Send the inverted image
    await message.channel.send(file=discord.File(f"inverted_image_{message_id}.png"))
    os.remove(f"inverted_image_{message_id}.png")


async def caption_image(image, message):
    if moondream_model is None:
        await message.channel.send(
            "Sorry, image descriptions are not available right now. "
            "The Moondream model was not loaded when the bot started. "
            f"Please ask the bot administrator to restart with the `{MOONDREAM_FLAG}` flag to enable this feature."
        )
        return

    start_time = time.time()  # Start measuring time
    caption = moondream_model.caption(image, length="normal")
    end_time = time.time()  # Stop measuring time
    elapsed_time = end_time - start_time
    reply_message = caption["caption"]
    # We now want to add a garbage can emoji reaction to the bots message
    # This will allow the user to delete the message if they want to

    # We need to get the message that the bot just sent
    new_message = await message.reply(reply_message)
    # We need to add the garbage can emoji to the message
    await new_message.add_reaction("🗑️")
    print(f"Captioning time: {elapsed_time:.2f}s", file=stderr)


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
        # Get the attachments and embeds
        attachments = message.attachments

        # Added feature by Kvysteran: Loop through the embeds and try to download the images.
        # Before this change, posts would sometimes appear to contain an image but were unable to be
        # processed because the image was a displayed embed from a pasted link and not an attachment.
        for embed in message.embeds:
            try:
                link = embed.image.proxy_url
                if link is None:
                    link = embed.thumbnail.proxy_url
                data = requests.get(link).content
                with Image.open(BytesIO(data)) as image:
                    if "invert_image" in emoji_name:
                        await invert_image(image, message)
                    if "image_desc" in emoji_name:
                        await caption_image(image, message)
            except:
                await message.channel.send(
                    "Uh-oh, it looks like this message has an embedded link but no actual attached images.\nI tried to follow the link and download the image, but something went wrong.  :("
                )

        # Loop through the attachments
        for attachment in attachments:
            # Check if the attachment is an image
            if attachment.content_type.startswith("image"):
                # Download the image
                await attachment.save(attachment.filename)
                # Read the image
                with Image.open(attachment.filename) as image:
                    if "invert_image" in emoji_name:
                        await invert_image(image, message)
                    if "image_desc" in emoji_name:
                        await caption_image(image, message)
                # Delete the images
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
        # Check if the message is a reply
        if not replied_message:
            return
        # Check if the replied message is owned by the user who reacted
        if replied_message.author != user:
            return

        # The only way we get here is if
        # - The reaction is the garbage can emoji
        # - The message is a reply
        # - The replied message is owned by the user who reacted

        # This means we can delete the message

        # Delete the message
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
        # Save the file
        await attachment.save(attachment.filename)
        audioMP3 = AudioSegment.from_ogg(attachment.filename)
        # Added feature by Kvysteran: convert the .ogg file to .mp3 before making the file available for download.
        # This makes playback of saved voice recordings easier for people that use Apple devices.
        # REQUIRED: the ffprobe executable must be placed in the same file location that this python program is running from.
        # If you have ffmpeg.exe but not ffprobe.exe, this conversion will fail and cause a crash.  :(
        filenameMP3 = attachment.filename.replace(".ogg", ".mp3")
        audioMP3.export(filenameMP3, format="mp3")
        # Send the file
        await message.channel.send(file=discord.File(filenameMP3))
        # Delete the file
        os.remove(attachment.filename)
        os.remove(filenameMP3)


client.run(os.getenv("BOT_TOKEN"))
