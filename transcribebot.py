import whisper
import discord
import os
from dotenv import load_dotenv
import traceback
import time
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
                        server_nickname = message.guild.get_member(message.author.id).display_name
                        reply_message = f"**{server_nickname}**: {transcribed_text}"

                        # We now want to add a garbage can emoji reaction to the bots message
                        # This will allow the user to delete the message if they want to

                        # We need to get the message that the bot just sent
                        new_message = await message.reply(reply_message)
                        # We need to add the garbage can emoji to the message
                        await new_message.add_reaction('🗑️')
                        
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
        
        # Check if the user is the bot
        if user == self.user:
            return
        
        # Check if the message was sent by the bot
        if reaction.message.author != self.user:
            return
        
        # Check if the reaction is the garbage can emoji
        if reaction.emoji != '🗑️':
            return
        
        # Check if the message the bot is replying to is owned by the user who reacted or an admin
        if reaction.message.reference:
            # Get the message the bot is replying to
            replied_message = await reaction.message.channel.fetch_message(reaction.message.reference.message_id)
            # Check if the replied message is owned by the user who reacted or an admin
            if replied_message.author != user and not user.guild_permissions.administrator:
                return
            
        # Delete the message
        await reaction.message.delete()
                    
intents = discord.Intents.default()
intents.message_content = True
# guilds is required to get the nickname of the user
intents.members = True

client = MyClient(intents=intents)
client.run(os.getenv('BOT_TOKEN'))