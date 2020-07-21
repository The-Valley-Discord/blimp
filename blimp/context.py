from enum import Enum
import logging
import sqlite3
from typing import Union

import discord
from discord.ext import commands


class BlimpContext(commands.Context):
    """
    A context that does other useful things.
    """

    ReplyColor = Enum("ReplyColor", ["GOOD", "I_GUESS", "BAD"])

    @classmethod
    def color(cls, color: ReplyColor) -> int:
        """Return the color appropriate for the ReplyColor supplied"""
        if color == cls.ReplyColor.GOOD:
            return 0x7DB358
        if color == cls.ReplyColor.I_GUESS:
            return 0xF9AE36
        if color == cls.ReplyColor.BAD:
            return 0xD52D48
        raise ValueError("Bad ReplyColor")

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
    def objects(self):
        """Return the bot's Objects cog."""
        return self.bot.get_cog("Objects")

    async def reply(
        self, msg: str, color: ReplyColor = ReplyColor.GOOD, embed: discord.Embed = None
    ):
        """Helper for sending embedded replies"""
        if not embed:
            await self.send(
                "", embed=discord.Embed(color=self.color(color), description=msg)
            )
        else:
            await self.send("", embed=embed)

    def privileged_modify(
        self, subject: Union[discord.TextChannel, discord.Member, discord.Guild]
    ) -> bool:
        """
        Check if the context's user can do privileged actions on the subject.
        """
        kind = subject.__class__
        if kind == discord.TextChannel:
            return self.author.permissions_for(subject).manage_messages
        if kind == discord.Member:
            return self.author.guild_permissions.ban_users
        if kind == discord.Guild:
            return self.author.guild_permissions.manage_guild

        raise ValueError("unsupported subject {kind}")
