"Actually the interesting file, init code lives here"

import base64
import logging
import re
import traceback
from configparser import ConfigParser
from importlib import metadata
from string import Template
from typing import Optional

import discord
from discord.ext import commands

from . import cogs
from .customizations import AnticipatedError, Blimp, PleaseRestate, Unauthorized

config = ConfigParser()
config.read("blimp.cfg")

logging.basicConfig(
    style="{", format="{levelname} {name}: {message}", level=config["log"]["level"]
)
for source in config["log"]["suppress"].split(","):
    logging.getLogger(source).addFilter(
        lambda row: row.levelno > getattr(logging, config["log"]["level"])
    )

intents = discord.Intents.default()
intents.members = True

bot = Blimp(
    config,
    case_insensitive=True,
    activity=Blimp.random_status(),
    help_command=None,
    intents=intents,
)
for cog in [
    cogs.Alias,
    cogs.Board,
    cogs.Logging,
    cogs.Slowmode,
    cogs.Malarkey,
    cogs.Meta,
    cogs.Moderation,
    cogs.Tickets,
    cogs.Tools,
    cogs.Triggers,
    cogs.WelcomeLog,
    cogs.Kiosk,
    cogs.Wizard,
    cogs.SIG,
]:
    bot.add_cog(cog(bot))


def process_docstrings(text) -> str:
    "Turn a raw function docstring into a help text for display"
    return re.sub(
        r"(.+)\n *",
        r"\1 ",
        Template(text).safe_substitute(
            {
                "manual": bot.config["info"]["manual"],
                "sfx": bot.config["discord"]["suffix"],
            }
        ),
    )


ONCE_LOCK = False


@bot.event
async def on_ready():
    "Hello world."
    bot.log.info(f"Logged in as {bot.user}")

    global ONCE_LOCK  # pylint: disable=global-statement
    if not ONCE_LOCK:
        bot.add_cog(cogs.Reminders(bot))
        bot.owner_id = (await bot.application_info()).owner.id

        # inserting runtime data into help
        for command in bot.walk_commands():
            command.help = process_docstrings(command.help)

        ONCE_LOCK = True


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
        link = discord.utils.oauth_url(
            ctx.bot.user.id, permissions=discord.Permissions(administrator=True)
        )
        embed.description = process_docstrings(
            f"""This is the *[BLIMP]({ctx.bot.config['info']['web']}) Levitating Intercommunication
            Management Programme*, a general-purpose management bot for Discord.


            For detailed help on any command, you can use `{signature(_help)}`. You may also find
            useful, but largely supplemental, information in the **[online manual]($manual)**. BLIMP
            is [open-source]({ctx.bot.config['info']['source']}). This instance runs version
            {metadata.version('blimp')} and is active on {len(ctx.bot.guilds)} servers with
            {len(ctx.bot.users)} members.

            You can invite BLIMP to your server using [this link]({link})."""
        )

        invite = ctx.bot.config["info"].get("support_invite")
        if invite:
            embed.description += f"\nYou can join the support server here: {invite}."

        all_commands = ""
        standalone_commands = ""
        previous_group = None
        for cmd in sorted(ctx.bot.walk_commands(), key=lambda x: x.qualified_name):
            if cmd.__class__ == commands.Command:
                if not cmd.parent:
                    standalone_commands += f"`{cmd.qualified_name}` "
                else:
                    if previous_group != cmd.parent:
                        all_commands += f"\n**`{cmd.parent.name}`** "
                    all_commands += f"`{cmd.name}` "

                previous_group = cmd.parent

        embed.add_field(
            name="All Commands", value=standalone_commands + "\n" + all_commands
        )

    else:
        for command in ctx.bot.walk_commands():
            if subject.casefold() in (
                command.qualified_name.casefold(),
                command.qualified_name.replace(ctx.bot.suffix, "").casefold(),
            ):
                embed.title = signature(command)
                embed.description = command.help

                if command.__class__ == commands.Group:
                    embed.description += "\n\n" + "\n\n".join(
                        signature(sub) + "\n" + sub.help.split("\n")[0]
                        for sub in command.commands
                    )

    await ctx.send(None, embed=embed)


@bot.event
async def on_command(ctx):
    "Log when we invoke commands"
    args = [
        arg
        for arg in ctx.args
        if not isinstance(arg, Blimp.Cog) and not isinstance(arg, Blimp.Context)
    ]
    args.extend(list(ctx.kwargs.values()))
    ctx.log.info(f"{ctx.author} invoked with {args}")


@bot.event
async def on_command_error(ctx, error):
    """
    Handle errors, delegating all "internal errors" (exceptions foreign to
    discordpy) to stderr and discordpy (i.e. high-level) errors to the user.
    """
    if isinstance(error, commands.CommandInvokeError) and isinstance(
        error.original, AnticipatedError
    ):
        original = error.original
        await ctx.reply(
            str(original),
            title=original.TEXT,
            color=ctx.Color.BAD,
            delete_after=5.0 if isinstance(original, Unauthorized) else None,
        )
        return
    elif isinstance(error, commands.UserInputError):
        await ctx.reply(
            str(error),
            title=PleaseRestate.TEXT,
            color=ctx.Color.BAD,
        )
        return
    elif isinstance(error, commands.CommandNotFound):
        return
    else:
        error_int = int(ctx.author.id) + int(ctx.message.id)
        error_bytes = error_int.to_bytes(
            (error_int.bit_length() + 7) // 8, byteorder="little"
        )
        error_id = str(
            base64.urlsafe_b64encode(error_bytes),
            encoding="utf-8",
        ).replace("=", "")

        ctx.log.error(
            f"Encountered exception while executing {ctx.command} [ID {error_id}]",
            exc_info=error,
        )

        try:
            channel_id = ctx.bot.config["log"].get("error_log_id")
            if channel_id:
                channel = ctx.bot.get_channel(int(channel_id))
                tb_lines = traceback.format_tb(error.__cause__.__traceback__)
                tb_lines = "".join(tb_lines)

                await channel.send(
                    f"Encountered exception while executing {ctx.command} [ID `{error_id}`]"
                    f"\n```py\n{error}\n{tb_lines}\n```"
                )

        except discord.HTTPException as ex:
            ctx.log.error(f"Couldn't send error to Discord: {ex}")

        await ctx.reply(
            f"If you report this bug, please give us this log ID: `{error_id}`",
            title="Unable to comply, internal error.",
            color=ctx.Color.BAD,
        )


def main():  # pylint: disable=missing-function-docstring
    bot.run(config["discord"]["token"])


if __name__ == "__main__":
    main()
