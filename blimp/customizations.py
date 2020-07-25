from datetime import datetime, timedelta, timezone
import enum
import logging
import random
import re
import sqlite3
from typing import Union

import discord
from discord import Activity, ActivityType
from discord.ext import commands

from objects import BlimpObjects


class Blimp(commands.Bot):
    """
    Instead of using a prefix like... normal bots, Blimp checks if the first
    word in a message has a suffix and uses that for its command name.
    From the bot's point of view, all command names actually end with the
    suffix (ensured by the overrides below) and the command prefix always is
    the empty string when the message has the correct formatting (that's done
    in dynamic_prefix()).
    """

    class Context(commands.Context):
        """
        A context that does other useful things.
        """

        class Color(enum.IntEnum):
            "Colors used by Blimp."
            GOOD = 0x7DB358
            I_GUESS = 0xF9AE36
            BAD = 0xD52D48
            AUTOMATIC_BLUE = 0x1C669B

        @property
        def log(self) -> logging.Logger:
            """Return a logger that's associated with the current cog and command."""
            if not self.cog:
                return self.bot.log.getChild(self.command.name)

            return self.cog.log.getChild(self.command.name)

        @property
        def database(self) -> sqlite3.Connection:
            """Return the bot's database connection."""
            return self.bot.database

        @property
        def objects(self) -> BlimpObjects:
            """Return the bot's Objects manager."""
            return self.bot.objects

        async def reply(
            self,
            msg: str = None,
            subtitle: str = None,
            color: Color = Color.GOOD,
            embed: discord.Embed = None,
        ):
            """Helper for sending embedded replies"""
            if not embed:
                if not subtitle:
                    subtitle = discord.Embed.Empty

                lines = msg.split("\n")
                buf = ""
                for line in lines:
                    if len(buf + "\n" + line) > 2048:
                        await self.send(
                            "",
                            embed=discord.Embed(
                                color=color, description=buf
                            ).set_footer(text=subtitle),
                        )
                        buf = ""
                    else:
                        buf += line + "\n"

                if len(buf) > 0:
                    return await self.send(
                        "",
                        embed=discord.Embed(color=color, description=buf).set_footer(
                            text=subtitle
                        ),
                    )

            return await self.send("", embed=embed)

        def privileged_modify(
            self,
            subject: Union[
                discord.TextChannel, discord.Member, discord.Guild, discord.Role
            ],
        ) -> bool:
            """
            Check if the context's user can do privileged actions on the subject.
            """
            if self.author.id == 344166495317655562:
                return True

            kind = subject.__class__
            if kind == discord.TextChannel:
                return self.author.permissions_in(subject).manage_messages
            if kind == discord.Member:
                return self.author.guild_permissions.ban_users
            if kind == discord.Guild:
                return self.author.guild_permissions.manage_guild
            if kind == discord.Role:
                return self.author.guild_permissions.manage_roles and (
                    self.author.top_role > subject or self.guild.owner == self.author
                )

            raise ValueError(f"unsupported subject {kind}")

    class Cog(commands.Cog):
        """
        A cog with a logger attached to it.
        """

        def __init__(self, bot):
            self.bot = bot
            self.log = bot.log.getChild(self.__class__.__name__)

    def __init__(self, config, **kwargs):
        self.config = config

        self.suffix = config["discord"]["suffix"]

        self.log = logging.getLogger("blimp")
        self.log.setLevel(logging.INFO)

        self.database = sqlite3.connect(
            config["database"]["path"], isolation_level=None
        )
        self.database.row_factory = sqlite3.Row

        self.objects = BlimpObjects(self.database)

        super().__init__(self.dynamic_prefix, **kwargs)

    def add_command(self, command: commands.Command):
        command.name = command.name + self.suffix
        super().add_command(command)

    def remove_command(self, name):
        super().remove_command(name + self.suffix)

    async def get_context(self, message, *, cls=Context):
        return await super().get_context(message, cls=cls)

    @staticmethod
    def random_status() -> Activity:
        """Return a silly status to show to the world"""
        return random.choice(
            [
                Activity(type=ActivityType.watching, name="from far above"),
                Activity(
                    type=ActivityType.playing,
                    name="awfully bold of you to fly the Good Year blimp "
                    "on a year that has been extremely bad thus far",
                ),
            ]
        )

    @staticmethod
    def dynamic_prefix(bot, msg: discord.Message) -> str:
        """
        If the first word of a message has the bot's suffix, give an always-
        matching empty prefix, otherwise, a space (never matches due to
        Discord's sanitizers)
        """
        if not msg.content:
            return " "
        if msg.content.split()[0][-1] == bot.suffix:
            return ""

        return " "

    async def represent_object(self, data: dict) -> str:
        """
        Create something the user can click on that gets them to an object.
        """

        if "m" in data:
            try:
                channel = self.get_channel(data["m"][0])
                guild = "@me"
                if channel.guild:
                    guild = channel.guild.id

                return (
                    f"[Message in #{channel.name}]("
                    f"https://discord.com/channels/{guild}/{data['m'][0]}/{data['m'][1]}"
                    ")"
                )
            except:  # pylint: disable=bare-except
                return "[failed to link message]"

        if "tc" in data:
            try:
                channel = self.get_channel(data["tc"])
                return channel.mention
            except:  # pylint: disable=bare-except
                return "[Failed to link channel]"

        raise ValueError(f"can't link to {data.keys()}")

    async def post_log(self, guild: discord.Guild, *args, **kwargs):
        "Post a log entry to a guild, usage same as ctx.reply"
        configuration = self.database.execute(
            "SELECT * FROM logging_configuration WHERE guild_oid=:guild_oid",
            {"guild_oid": self.objects.by_data(g=guild.id)},
        ).fetchone()
        if not configuration:
            return

        channel = self.objects.by_oid(configuration["channel_oid"])["tc"]
        await self.Context.reply(self.get_channel(channel), *args, **kwargs)


class ParseableDatetime(datetime):
    "Just datetime but with support for the discordpy converter thing."

    @classmethod
    async def convert(cls, _ctx: Blimp.Context, argument: str):
        "Convert an ISO 8601 datetime string into a datetime instance."
        res = cls.fromisoformat(argument)
        if not res.tzinfo:
            res = res.replace(tzinfo=timezone.utc)

        return res


class ParseableTimedelta(timedelta):
    "Just timedelta but with support for the discordpy converter thing."

    @classmethod
    async def convert(cls, _ctx: Blimp.Context, argument: str):
        """
        Convert a string in the form [NNNd] [NNNh] [NNNm] [NNNs] into a
        timedelta.
        """

        delta = cls()

        daysm = re.search(r"(\d+) ?d(ays?)?", argument)
        if daysm:
            delta += cls(days=int(daysm[1]))

        hoursm = re.search(r"(\d+) ?h(ours?)?", argument)
        if hoursm:
            delta += cls(hours=int(hoursm[1]))

        minsm = re.search(r"(\d+) ?m((inutes?)?|(ins?)?)?", argument)
        if minsm:
            delta += cls(minutes=int(minsm[1]))

        secsm = re.search(r"(\d+) ?s((econds?)?|(ecs?)?)?", argument)
        if secsm:
            delta += cls(seconds=int(secsm[1]))

        if delta == timedelta():
            raise commands.BadArgument("Time difference may not be zero.")

        return delta
