"""
Actually the interesting file, init code lives here
"""

from configparser import ConfigParser
import logging

import discord
from discord.ext import commands

from bot import Blimp
import cogs

config = ConfigParser()
config.read("blimp.cfg")

logging.basicConfig(
    style="{", format="{levelname} {name}: {message}", level=config["log"]["level"]
)
for source in config["log"]["suppress"].split(","):
    logging.getLogger(source).addFilter(
        lambda row: row.levelno > getattr(logging, config["log"]["level"])
    )

bot = Blimp(
    suffix="!",
    database_path=config["database"]["path"],
    case_insensitive=True,
    activity=discord.Activity(
        type=discord.ActivityType.watching, name="from far above"
    ),
)
for cog in [cogs.RoleKiosk, cogs.Objects]:
    bot.add_cog(cog(bot))


@bot.event
async def on_ready():
    """Hello world."""
    bot.log.info(f"Logged in as {bot.user}")


@bot.event
async def on_command_error(ctx: commands.Context, error):
    """
    Handle errors, delegating all "internal errors" (exceptions foreign to
    discordpy) to stderr and discordpy (i.e. high-level) errors to the user.
    """
    if error.__class__ == commands.CommandInvokeError:
        ctx.log.error(
            f"Encountered exception during executing {ctx.command}", exc_info=error
        )
        await ctx.send(f"{Blimp.BAD} *Internal Error.*")
    else:
        await ctx.send(f"{Blimp.BAD} *Error: {error}*")


bot.run(config["discord"]["token"])
