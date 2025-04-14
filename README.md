# Necho

A Discord bot for audio and image accessibility.

Based on MLFinley's transcribe-bot, which is now on gitlab:

https://git.mlfinley.com/molly/transcribe-bot

Updates to image inversion by Kvysteran.

## Features
- Automatically transcribe voice memos
- Invert attached images to reduce visual strain
- Caption attached images to provide descriptions

## Models used
- OpenAI Whisper
- Moondream

## Setup
ffmpeg.exe and ffprobe.exe must be in the same directory as the script.

To run the models on the GPU, additionally install a compatible version of PyTorch.

1. Clone the repository
2. Create a virtual environment
3. Install the requirements `pip install -r requirements.txt`
4. Add your bot token to a `bot_params.env` file
5. Run the bot `python transcribebot.py`
6. Invite the bot to your server
