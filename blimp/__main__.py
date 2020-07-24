"""
Actually the interesting file, init code lives here
"""

from configparser import ConfigParser
import logging
from typing import Optional

import discord
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
    config, case_insensitive=True, activity=Blimp.random_status(), help_command=None,
)
for cog in [
    cogs.RoleKiosk,
    cogs.Aliasing,
    cogs.Welcome,
    cogs.Board,
    cogs.Reminders,
    cogs.Malarkey,
    cogs.Tools,
    cogs.Logging,
]:
    bot.add_cog(cog(bot))


@bot.event
async def on_ready():
    """Hello world."""
    bot.log.info(f"Logged in as {bot.user}")


@bot.command(name="help")
async def _help(ctx: Blimp.Context, *, subject: Optional[str]):
    "Display the usage of commands."

    def signature(cmd: commands.Command) -> str:
        out = f"`{cmd.qualified_name}"
        if cmd.signature:
            out += " " + cmd.signature
        out += "`"
        return out

    embed = discord.Embed(color=ctx.Color.I_GUESS, title="BLIMP Manual")
    if not subject:
        embed.description = (
            f"This is the *[BLIMP]({ctx.bot.config['info']['web']}) "
            "Levitating Intercommunication Management Programme*, a management "
            f"bot for Discord.\nFor detailed help, use `{signature(_help)}`"
            "with individual commands or any of the larger features "
            "listed below.\nThere's also an [online manual]"
            f"({ctx.bot.config['info']['manual']}) and, of course, the [source "
            f"code]({ctx.bot.config['info']['source']})."
        )
        embed.add_field(name="Core", value=signature(_help))

        for name, cog in ctx.bot.cogs.items():  # pylint: disable=redefined-outer-name
            all_commands = []
            for command in cog.get_commands():
                if isinstance(command, commands.Group):
                    all_commands.extend([signature(sub) for sub in command.commands])
                else:
                    all_commands.append(signature(command))

            embed.add_field(
                name=name,
                value=cog.description.split("\n")[0]
                + "\n"
                + "\n".join(sorted(all_commands)),
                inline=False,
            )
    else:
        for name, cog in ctx.bot.cogs.items():
            if subject.casefold() == name.casefold():
                field = ""
                for command in cog.get_commands():
                    field += "\n"
                    if isinstance(command, commands.Group):
                        field += "\n".join(
                            [
                                f"{signature(sub)}\n{sub.short_doc}"
                                for sub in command.commands
                            ]
                        )
                    else:
                        field += f"{signature(command)}\n{command.short_doc}\n"
                embed.add_field(
                    name=f"Feature: {name}",
                    value=cog.description + "\n" + field,
                    inline=False,
                )
        for command in ctx.bot.walk_commands():
            if subject.casefold() in (
                command.qualified_name.casefold(),
                command.qualified_name.replace(ctx.bot.suffix, "").casefold(),
            ):
                embed.add_field(
                    name=f"Command: {signature(command)}",
                    value=command.help,
                    inline=False,
                )

    await ctx.send(None, embed=embed)


@bot.event
async def on_command_error(ctx, error):
    """
    Handle errors, delegating all "internal errors" (exceptions foreign to
    discordpy) to stderr and discordpy (i.e. high-level) errors to the user.
    """
    if isinstance(error, commands.CommandInvokeError):
        ctx.log.error(
            f"Encountered exception during executing {ctx.command}", exc_info=error
        )
        await ctx.reply(
            "*soon questions arise:*\n"
            "*me unwilling, what did you*\n"
            "*want in the first place?*",
            subtitle="Internal Error.",
            color=ctx.Color.BAD,
        )
    elif isinstance(error, commands.CommandNotFound):
        return
    else:
        await ctx.reply(
            "*here's news, good and bad:*\n"
            "*the bad, something clearly broke.*\n"
            "*the good? not my fault.*",
            subtitle=f"Error: {error}",
            color=ctx.Color.BAD,
        )


bot.run(config["discord"]["token"])
