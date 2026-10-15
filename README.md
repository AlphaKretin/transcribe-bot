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

1. Install [LibVips](https://www.libvips.org/)
2. Clone the repository
3. Create a virtual environment `python -m venv .venv`
4. Install the requirements `pip install -r requirements.txt`
5. To run the models on an NVIDIA GPU, also install
   `pip install -r requirements-gpu.txt`
6. Add your bot token to a `bot_params.env` file
7. Run the bot `python transcribebot.py`
8. Invite the bot to your server
