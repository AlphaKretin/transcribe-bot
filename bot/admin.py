import asyncio
import logging
import secrets
import time
from typing import Literal

import discord
from discord import app_commands

from bot import models

log = logging.getLogger(__name__)


async def is_owner(client, user):
    """Whether user owns the bot's application, or is on the team that does."""
    app = await client.application_info()
    if app.team:
        return any(member.id == user.id for member in app.team.members)
    return app.owner.id == user.id


async def reply(interaction, text):
    if interaction.response.is_done():
        await interaction.followup.send(text, ephemeral=True)
    else:
        await interaction.response.send_message(text, ephemeral=True)


@app_commands.command(description="Turn image descriptions (Moondream) on or off")
@app_commands.describe(action="on loads the model, off unloads it")
async def moondream(interaction: discord.Interaction, action: Literal["on", "off"]):
    user = interaction.user
    if not await is_owner(interaction.client, user):
        await reply(interaction, "Sorry, only the bot owner can do this.")
        return
    if models.moondream_loading:
        await reply(
            interaction, "Moondream is still loading, try again once it's done."
        )
        return

    if action == "off":
        if models.moondream_model is None:
            await reply(interaction, "Moondream is already off.")
            return
        models.unload_moondream()
        log.info("Moondream turned off by %s (%s)", user, user.id)
        await reply(interaction, "Moondream is off.")
        return

    if models.moondream_model is not None:
        await reply(interaction, "Moondream is already on.")
        return
    await interaction.response.defer(ephemeral=True, thinking=True)
    log.info("Moondream turned on by %s (%s)", user, user.id)
    models.moondream_loading = True
    start_time = time.time()
    try:
        await asyncio.to_thread(models.load_moondream)
    except Exception:
        error_id = secrets.token_hex(3)
        log.exception("Couldn't load Moondream (error ID %s)", error_id)
        await reply(interaction, f"Loading Moondream failed, error ID `{error_id}`.")
        return
    finally:
        models.moondream_loading = False
    await reply(
        interaction, f"Moondream is on (loaded in {time.time() - start_time:.0f}s)."
    )
