import whisper
import discord
import os
from dotenv import load_dotenv
import traceback
import time
import numpy as np
from PIL import Image, ImageOps
from sys import stderr

load_dotenv()

model_size = os.getenv("MODEL_SIZE") or "base"

print('Using Model Size:',model_size,file=stderr)

model = whisper.load_model(model_size)

username = 'TranscribeBot'

class MyClient(discord.Client):
    async def on_ready(self):
        print(f'Logged on as {self.user}!')

    async def on_message(self, message):
        # don't respond to ourselves
        if message.author == self.user:
            return

        if message.attachments:
            for attachment in message.attachments:
                if attachment.filename == 'voice-message.ogg':
                    file_name = attachment.filename
                    # add message id to file name
                    file_name = f'{message.id}-{file_name}'
                    try:
                        # save the file
                        await attachment.save(file_name)
                        print(f'Saved attachment: {file_name}')
                        
                        start_time = time.time()  # Start measuring time
                        
                        text = whisper.transcribe(model, file_name)
                        transcribed_text = text['text'].strip()
                        
                        end_time = time.time()  # Stop measuring time
                        elapsed_time = end_time - start_time
                        
                        # get the user's nickname
                        if message.guild:
                            server_nickname = message.guild.get_member(message.author.id).display_name
                            reply_message = f"**{server_nickname}**: {transcribed_text}"
                        else:
                            reply_message = transcribed_text
                    
                        # We now want to add a garbage can emoji reaction to the bots message
                        # This will allow the user to delete the message if they want to

                        # We need to get the message that the bot just sent
                        new_message = await message.reply(reply_message)
                        # We need to add the garbage can emoji to the message
                        await new_message.add_reaction('🗑️')
                        await new_message.add_reaction('⬇️')
                        
                        print(f'Transcription time: {elapsed_time:.2f}s', file=stderr)
                        
                    except Exception as e:
                        traceback.print_exc()
                    finally:
                        # delete the file
                        os.remove(file_name)
    # This function is called when a reaction is added to a message
    async def on_reaction_add(self, reaction, user):
        '''
        We want to delete the message if
         - The user reacts with the garbage can emoji
         - The message was sent by the bot
         - The message the bot is replying to is owned by the user who reacted or an admin
        '''
        if 'invert_image' in str(reaction.emoji):
            # Get the attachments
            attachments = reaction.message.attachments
            # Check if there are attachments
            if not attachments:
                return
            # Loop through the attachments
            for attachment in attachments:
                # Check if the attachment is an image
                if attachment.content_type.startswith('image'):
                    # Download the image
                    await attachment.save(attachment.filename)
                    # Read the image
                    with Image.open(attachment.filename) as image:
                        # if the image is RGBA, convert it to RGB
                        if image.mode == "RGBA":
                            r, g, b, a = image.split()
                            image = Image.merge("RGB", (r, g, b))
                        # Invert the image
                        inverted_image = ImageOps.invert(image)
                        # Save the inverted image
                        # Get message id
                        message_id = reaction.message.id
                        inverted_image.save(f"inverted_image_{message_id}.png")
                        # Send the inverted image
                        await reaction.message.channel.send(
                            file=discord.File(f"inverted_image_{message_id}.png")
                        )
                        os.remove(f"inverted_image_{message_id}.png")
                    # Delete the images
                    os.remove(attachment.filename)

        # Check if the user is the bot
        if user == self.user:
            return
        
        # Check if the message was sent by the bot
        if reaction.message.author != self.user:
            return

        # Check if the message is a reply
        if reaction.message.reference:
            # Get the message the bot is replying to
            replied_message = await reaction.message.channel.fetch_message(reaction.message.reference.message_id)
        else:
            replied_message = None

        # Check if the reaction is the garbage can emoji
        if reaction.emoji == '🗑️':
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
            await reaction.message.delete()
        
        # Check if the reaction is the download emoji
        if reaction.emoji == '⬇️':
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
            # Send the file
            await reaction.message.channel.send(file=discord.File(attachment.filename))
            # Delete the file
            os.remove(attachment.filename)

                    
intents = discord.Intents.default()
intents.message_content = True
# guilds is required to get the nickname of the user
intents.members = True

client = MyClient(intents=intents)
client.run(os.getenv('BOT_TOKEN'))
