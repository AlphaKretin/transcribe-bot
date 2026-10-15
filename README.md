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

ffmpeg.exe and ffprobe.exe must be in the same directory as the script. You will
also need to instal [LibVips](https://www.libvips.org/).

1. Clone the repository
2. Create a virtual environment `python -m venv .venv`
3. Install the requirements `pip install -r requirements.txt`
4. To run the models on an NVIDIA GPU, also install
   `pip install -r requirements-gpu.txt`
5. Add your bot token to a `bot_params.env` file
6. Run the bot `python transcribebot.py`
7. Invite the bot to your server
