import logging
import sqlite3

import discord
from discord.ext import commands

from context import BlimpContext


class Blimp(commands.Bot):
    """
    Instead of using a prefix like... normal bots, Blimp checks if the first
    word in a message has a suffix and uses that for its command name.
    From the bot's point of view, all command names actually end with the
    suffix (ensured by the overrides below) and the command prefix always is
    the empty string when the message has the correct formatting (that's done
    in dynamic_prefix()).
    """

    def __init__(self, suffix, database_path, **kwargs):
        self.suffix = suffix

        self.log = logging.getLogger("blimp")
        self.log.setLevel(logging.INFO)

        self.database = sqlite3.connect(database_path, isolation_level=None)
        self.database.row_factory = sqlite3.Row

        super().__init__(self.dynamic_prefix, **kwargs)

    def add_command(self, command: commands.Command):
        command.name = command.name + self.suffix
        super().add_command(command)

    def remove_command(self, name):
        super().remove_command(name + self.suffix)

    async def get_context(self, message, *, cls=BlimpContext):
        return await super().get_context(message, cls=cls)

    @staticmethod
    def dynamic_prefix(bot, msg: discord.Message) -> str:
        """
        If the first word of a message has the bot's suffix, give an always-
        matching empty prefix, otherwise, a space (never matches due to
        Discord's sanitizers)
        """
        if msg.content.split()[0][-1] == bot.suffix:
            return ""

        return " "


class BlimpCog(commands.Cog):
    """
    A cog with a logger attached to it.
    """

    def __init__(self, bot: Blimp):
        self.bot = bot
        self.log = bot.log.getChild(self.__class__.__name__)
