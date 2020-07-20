import json
import sqlite3
from typing import Union

import discord
from discord.ext import commands
from discord.ext.commands import UserInputError

from bot import Blimp, BlimpCog
from context import BlimpContext


class Objects(BlimpCog):
    """
    Internal "object" manager for Blimp. Powers aliasing.
    """

    def alias_to_object(self, guild_id: int, alias: str) -> sqlite3.Row:
        """Get the object behind an alias for the specified guild."""
        alias_cursor = self.bot.database.execute(
            "SELECT * FROM aliases WHERE gid=:gid AND alias=:alias",
            {"gid": guild_id, "alias": alias},
        )
        alias = alias_cursor.fetchone()
        if not alias:
            return None

        cursor = self.bot.database.execute(
            "SELECT * FROM objects WHERE oid=:oid", {"oid": alias["oid"]},
        )
        return cursor.fetchone()

    async def object_link(self, row: sqlite3.Row) -> str:
        """
        Create something the user can click on that gets them to the object.
        """
        data = json.loads(row["data"])
        if data["m"]:
            channel = self.bot.get_channel(data["m"][0])
            if not channel:
                return "[Failed to link]"

            return (await channel.fetch_message(data["m"][1])).jump_url

        raise ValueError("Bad object")

    def make_object(self, data: dict) -> int:
        """
        Create an object (do nothing if exists) and return its oid.
        """
        cursor = self.bot.database.execute(
            "INSERT OR REPLACE INTO objects(data) VALUES(json(:data));",
            {"data": json.dumps(data)},
        )
        return cursor.lastrowid

    def find_object(self, data: dict) -> int:
        """
        Find an object and return its oid or None.
        """
        cursor = self.bot.database.execute(
            "SELECT * FROM objects WHERE data=json(:data)", {"data": json.dumps(data)}
        )
        obj = cursor.fetchone()

        if not obj:
            return None
        return obj["oid"]

    @staticmethod
    def validate_alias(string) -> None:
        """Check if something should be allowed to be an alias."""
        if len(string) < 2 or string[0] != "'":
            raise ValueError(
                "Aliases must start with ' and have at least one character after that."
            )
        if len([ch for ch in string if ch.isspace()]) > 0:
            raise ValueError("Aliases may not contain whitespace.")

    @commands.group()
    async def alias(self, ctx: BlimpContext):
        """
        Aliases for things so you don't always have to grab their ID
        """

    @commands.command(parent=alias)
    async def make(self, ctx: BlimpContext, target: Union[discord.Message], alias: str):
        """
        Create an alias for a Discord object (messages, channels).
        Aliases must start with a single ', have no whitespace, and be unique.
        """
        if not ctx.privileged_modify(ctx.guild):
            return

        self.validate_alias(alias)

        ctx.database.execute("BEGIN TRANSACTION;")

        oid = None
        if target.__class__ == discord.Message:
            oid = self.make_object({"m": [target.channel.id, target.id]})
        else:
            raise ValueError("Bad object")

        try:
            ctx.database.execute(
                "INSERT OR ROLLBACK INTO aliases(gid, alias, oid) VALUES(:gid, :alias, :oid);",
                {"gid": ctx.guild.id, "alias": alias, "oid": oid},
            )
        except sqlite3.DatabaseError:
            raise UserInputError("That alias already exists.")

        ctx.database.execute("COMMIT;")

        new_cursor = ctx.database.execute(
            "SELECT * FROM objects WHERE oid=:oid", {"oid": oid},
        )
        link = await self.object_link(new_cursor.fetchone())
        await ctx.send(f"{Blimp.OKAY} *{link} is now known as {alias}.*")

    @commands.command(parent=alias)
    async def delete(self, ctx: BlimpContext, alias: str):
        """
        Delete an alias, freeing it up for renewed use.
        """

        if not ctx.privileged_modify(ctx.guild):
            return

        if not len(alias) > 2 or not alias[0] == "'":
            raise UserInputError(
                "Aliases must start with ' and have at least one character after that."
            )

        cursor = ctx.database.execute(
            "SELECT * FROM objects_aliases WHERE gid=:gid AND alias=:alias",
            {"gid": ctx.guild.id, "alias": alias},
        )
        old = cursor.fetchone()
        if not old:
            raise UserInputError("That alias doesn't exist.")

        link = await self.object_link(old)

        ctx.database.execute(
            "DELETE FROM objects_aliases WHERE gid=:gid AND alias=:alias",
            {"gid": ctx.guild.id, "alias": alias},
        )

        await ctx.send(f"{Blimp.OKAY} *Deleted alias `{alias}` (was {link}).*")

    @commands.command(parent=alias)
    async def list(self, ctx: BlimpContext):
        """
        List all aliases currently configured for this server.
        """
        cursor = ctx.database.execute(
            "SELECT * FROM aliases WHERE gid=:gid", {"gid": ctx.guild.id}
        )
        data = [
            (alias["alias"], self.alias_to_object(ctx.guild.id, alias["alias"]))
            for alias in cursor.fetchall()
        ]
        result = "\n".join([f"{d[0]}: <{await self.object_link(d[1])}>" for d in data])
        if not result:
            result = f"{Blimp.I_GUESS} *No aliases configured.*"
        await ctx.send(result)
