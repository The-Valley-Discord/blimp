"""
Actually the interesting file, init code lives here
"""

from configparser import ConfigParser
import logging

from discord.ext import commands

from customizations import Blimp
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
    suffix=config["discord"]["suffix"],
    database_path=config["database"]["path"],
    case_insensitive=True,
    activity=Blimp.random_status(),
)
for cog in [cogs.RoleKiosk, cogs.Aliasing, cogs.Welcome, cogs.Board, cogs.Reminders]:
    bot.add_cog(cog(bot))


@bot.event
async def on_ready():
    """Hello world."""
    bot.log.info(f"Logged in as {bot.user}")


@bot.event
async def on_command_error(ctx, error):
    """
    Handle errors, delegating all "internal errors" (exceptions foreign to
    discordpy) to stderr and discordpy (i.e. high-level) errors to the user.
    """
    if error.__class__ == commands.CommandInvokeError:
        ctx.log.error(
            f"Encountered exception during executing {ctx.command}", exc_info=error
        )
        await ctx.reply(
            """*soon questions arise:*
            *me unwilling, what did you*
            *want in the first place?*""",
            subtitle="Internal Error.",
            color=ctx.Color.BAD,
        )
    else:
        await ctx.reply(
            """*here's news, good and bad:*
            *the bad, something clearly broke.*
            *the good? not my fault.*""",
            subtitle=f"Error: {error}",
            color=ctx.Color.BAD,
        )


bot.run(config["discord"]["token"])
