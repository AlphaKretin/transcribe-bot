import whisper
import discord
import os
from dotenv import load_dotenv
import traceback
load_dotenv()

model = whisper.load_model("base")

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
                        text = whisper.transcribe(model, file_name)
                        transcribed_text = text['text'].strip()
                        # get the users nickname
                        server_nickname = message.guild.get_member(message.author.id).display_name
                        reply_message = f"**{server_nickname}**: {transcribed_text}"
                        await message.reply(reply_message)
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
client.run(os.getenv('BOT_TOKEN'))