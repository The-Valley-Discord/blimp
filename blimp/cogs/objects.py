import json
import sqlite3
from typing import Union

import discord
from discord.ext import commands
from discord.ext.commands import UserInputError

from bot import BlimpCog
from context import BlimpContext


class Objects(BlimpCog):
    """
    Internal "object" manager for Blimp. Powers aliasing.
    """

    def by_alias(self, guild_id: int, alias: str) -> sqlite3.Row:
        """Get the object behind an alias for the specified guild."""
        alias_cursor = self.bot.database.execute(
            "SELECT * FROM aliases WHERE gid=:gid AND alias=:alias",
            {"gid": guild_id, "alias": alias},
        )
        alias = alias_cursor.fetchone()
        if not alias:
            return None

        return self.by_oid(alias["oid"])

    def by_data(self, **kwargs) -> int:
        """
        Find an object and return its oid or None.
        """
        cursor = self.bot.database.execute(
            "SELECT * FROM objects WHERE data=json(:data)", {"data": json.dumps(kwargs)}
        )
        obj = cursor.fetchone()

        if not obj:
            return None
        return obj["oid"]

    def by_oid(self, oid: int) -> sqlite3.Row:
        """
        Find an object by oid or None.
        """
        cursor = self.bot.database.execute(
            "SELECT * FROM objects WHERE oid=:oid", {"oid": oid}
        )
        return cursor.fetchone()

    def data(self, row: sqlite3.Row) -> dict:
        """Extract the data from an object."""
        return json.loads(row["data"])

    async def representation(self, row: sqlite3.Row) -> str:
        """
        Create something the user can click on that gets them to the object.
        """
        data = json.loads(row["data"])

        if "m" in data:
            try:
                channel = self.bot.get_channel(data["m"][0])
                url = (await channel.fetch_message(data["m"][1])).jump_url
                return f"[Message in #{channel.name}]({url})"
            except:  # pylint: disable=bare-except
                return "[Failed to link message]"

        if "tc" in data:
            try:
                channel = self.bot.get_channel(data["tc"])
                return channel.mention
            except:  # pylint: disable=bare-except
                return "[Failed to link channel]"

        raise ValueError(f"can't link to {data.keys()}")

    def make_object(self, **kwargs) -> int:
        """
        INSERT OR IGNORE an object and return its oid.
        """
        old = self.by_data(**kwargs)
        if old:
            return old

        cursor = self.bot.database.execute(
            "INSERT INTO objects(data) VALUES(json(:data))",
            {"data": json.dumps(kwargs)},
        )
        return cursor.lastrowid

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
    async def make(
        self,
        ctx: BlimpContext,
        target: Union[discord.Message, discord.TextChannel],
        alias: str,
    ):
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
            oid = self.make_object(m=[target.channel.id, target.id])
        elif target.__class__ == discord.TextChannel:
            oid = self.make_object(tc=target.id)
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

        link = await self.representation(self.by_oid(oid))
        await ctx.reply(f"*{link} is now known as {alias}.*")

    @commands.command(parent=alias)
    async def delete(self, ctx: BlimpContext, alias: str):
        """
        Delete an alias, freeing it up for renewed use.
        """

        if not ctx.privileged_modify(ctx.guild):
            return

        self.validate_alias(alias)

        old = self.by_alias(ctx.guild.id, alias)

        ctx.database.execute(
            "DELETE FROM aliases WHERE gid=:gid AND alias=:alias",
            {"gid": ctx.guild.id, "alias": alias},
        )

        await ctx.reply(
            f"*Deleted alias `{alias}` (was {await self.representation(old)}).*"
        )

    @commands.command(parent=alias)
    async def list(self, ctx: BlimpContext):
        """
        List all aliases currently configured for this server.
        """
        cursor = ctx.database.execute(
            "SELECT * FROM aliases WHERE gid=:gid", {"gid": ctx.guild.id}
        )
        data = [
            (alias["alias"], self.by_alias(ctx.guild.id, alias["alias"]))
            for alias in cursor.fetchall()
        ]
        result = "\n".join([f"{d[0]}: {await self.representation(d[1])}" for d in data])
        if not result:
            await ctx.reply("*No aliases configured.*", color=ctx.Color.I_GUESS)
        else:
            await ctx.reply(result)
