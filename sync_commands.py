"""Register the bot's slash commands with Discord.

Run once after adding, removing or changing a command, not on every start:
    python sync_commands.py
Reads BOT_TOKEN from bot_params.env, like the bot. Global commands can take a few minutes
to show up, and the Discord app may need restarting to see them.
"""

import asyncio
import os

import discord
from dotenv import load_dotenv

from bot.client import BotClient


async def main():
    load_dotenv("bot_params.env")
    client = BotClient(intents=discord.Intents.none())
    async with client:
        await client.login(os.getenv("BOT_TOKEN") or "")
        synced = await client.tree.sync()
    print("Synced:", ", ".join(f"/{command.name}" for command in synced) or "nothing")


if __name__ == "__main__":
    asyncio.run(main())
