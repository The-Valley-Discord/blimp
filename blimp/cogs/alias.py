import sqlite3
from typing import Tuple, Union

import discord
from discord.ext import commands

from ..customizations import Blimp, UnableToComply, Unauthorized


class Alias(Blimp.Cog):
    "Giving names to things."

    @staticmethod
    def validate_alias(string) -> None:
        """Check if something should be allowed to be an alias."""
        if len(string) < 2 or string[0] != "'":
            raise UnableToComply(
                f"Alias {string} does not consist of an apostrophe followed by at least one "
                "character."
            )
        if len([ch for ch in string if ch.isspace()]) > 0:
            raise UnableToComply(f"Alias {string} contains whitespace.")

    @commands.group(invoke_without_command=True, case_insensitive=True)
    async def alias(self, ctx: Blimp.Context):
        """Aliases allow you to refer to e.g. messages or channels using simple, server-specific
        codes like `'rules` or `'the_bread_message`. This way you don't need to remember unwieldly
        Discord IDs like `526166150749618178`."""

        await ctx.invoke_command("alias list")

    @commands.command(parent=alias)
    async def make(
        self,
        ctx: Blimp.Context,
        target: Union[discord.Message, discord.TextChannel, discord.CategoryChannel],
        alias: str,
    ):
        """
        Create an alias to refer to a Discord object.

        `target` may be a message, a text channel, or a category.

        `alias` must start with an apostrophe `'` and contain no whitespace, but is otherwise
        entirely your choice.
        """
        if not ctx.privileged_modify(ctx.guild):
            raise Unauthorized()

        self.validate_alias(alias)

        ctx.database.execute("BEGIN TRANSACTION;")

        oid = None
        if target.__class__ == discord.Message:
            oid = ctx.objects.make_object(m=[target.channel.id, target.id])
        elif target.__class__ == discord.TextChannel:
            oid = ctx.objects.make_object(tc=target.id)
        elif target.__class__ == discord.CategoryChannel:
            oid = ctx.objects.make_object(cc=target.id)
        else:
            raise ValueError("Bad object")

        try:
            ctx.database.execute(
                "INSERT OR ROLLBACK INTO aliases(gid, alias, oid) VALUES(:gid, :alias, :oid);",
                {"gid": ctx.guild.id, "alias": alias, "oid": oid},
            )
        except sqlite3.DatabaseError as ex:
            ctx.database.execute("ABORT;")
            raise UnableToComply(f"Alias {alias} is already registered.") from ex

        ctx.database.execute("COMMIT;")

        link = await ctx.bot.represent_object(ctx.objects.by_oid(oid))
        await ctx.reply(f"*{link} is now known as {alias}.*")

    @commands.command(parent=alias)
    async def delete(self, ctx: Blimp.Context, alias: str):
        """Delete an alias, freeing it up for renewed use.

        `alias` must have been registered as an alias before."""

        if not ctx.privileged_modify(ctx.guild):
            raise Unauthorized()

        self.validate_alias(alias)

        old = ctx.objects.by_alias(ctx.guild.id, alias)
        if not old:
            raise UnableToComply(f"Alias {alias} doesn't exist.")

        ctx.database.execute(
            "DELETE FROM aliases WHERE gid=:gid AND alias=:alias",
            {"gid": ctx.guild.id, "alias": alias},
        )

        await ctx.reply(
            f"*Deleted alias `{alias}` (was {await ctx.bot.represent_object(old[1])}).*"
        )

    @commands.command(parent=alias, name="list")
    async def _list(self, ctx: Blimp.Context):
        "List all aliases currently configured for this server."

        cursor = ctx.database.execute(
            "SELECT * FROM aliases WHERE gid=:gid", {"gid": ctx.guild.id}
        )
        data = [
            (alias["alias"], ctx.objects.by_alias(ctx.guild.id, alias["alias"])[1])
            for alias in cursor.fetchall()
        ]
        result = "\n".join(
            [f"{d[0]}: {await ctx.bot.represent_object(d[1])}" for d in data]
        )
        if not result:
            await ctx.reply("*There are no aliases configured in this server.*")
            return

        await ctx.reply(result)


def find_aliased_message_id(ctx: Blimp.Context, argument: str) -> Tuple[int, int]:
    "Return a (channelid, messageid) tuple for an aliased message or raise commands.BadArgument."

    row = ctx.objects.by_alias(ctx.guild.id, argument)
    if not row:
        raise commands.BadArgument(f"Unknown alias {argument}.")

    if not row[1].get("m"):
        raise commands.BadArgument(f"Alias {argument} doesn't refer to a message.")

    return tuple(row[1]["m"])


class MaybeAliasedMessage(discord.Message):
    """An alias-aware converter for Messages."""

    @classmethod
    async def convert(cls, ctx: Blimp.Context, argument: str):
        """
        Convert an alias to a message or fall back to the message converter.
        """
        if not ctx.guild or not len(argument) > 1 or not argument[0] == "'":
            return await commands.MessageConverter().convert(ctx, argument)

        channelid, messageid = find_aliased_message_id(ctx, argument)
        return await commands.MessageConverter().convert(
            ctx, f"{channelid}-{messageid}"
        )


def find_aliased_channel_id(ctx: Blimp.Context, argument: str) -> int:
    "Return the id for an aliased channel or raise commands.BadArgument."
    row = ctx.objects.by_alias(ctx.guild.id, argument)
    if not row:
        raise commands.BadArgument(f"Unknown alias {argument}.")

    if not row[1].get("tc"):
        raise commands.BadArgument(f"Alias {argument} doesn't refer to a text channel.")

    return row[1]["tc"]


class MaybeAliasedTextChannel(discord.TextChannel):
    """An alias-aware converter for TextChannels."""

    @classmethod
    async def convert(cls, ctx: Blimp.Context, argument: str):
        """
        Convert an alias to a channel or fall back to the TextChannel converter.
        """
        if not ctx.guild or not len(argument) > 1 or not argument[0] == "'":
            return await commands.TextChannelConverter().convert(ctx, argument)

        channelid = find_aliased_channel_id(ctx, argument)
        return await commands.TextChannelConverter().convert(ctx, str(channelid))


def find_aliased_category_id(ctx: Blimp.Context, argument: str) -> int:
    "Return the id for an aliased category or raise commands.BadArgument."
    row = ctx.objects.by_alias(ctx.guild.id, argument)
    if not row:
        raise commands.BadArgument(f"Unknown alias {argument}.")

    if not row[1].get("cc"):
        raise commands.BadArgument(f"Alias {argument} doesn't refer to a category.")

    return row[1]["cc"]


class MaybeAliasedCategoryChannel(discord.CategoryChannel):
    """An alias-aware converter for CategoryChannels."""

    @classmethod
    async def convert(cls, ctx: Blimp.Context, argument: str):
        """
        Convert an alias to a channel or fall back to the CategoryChannel converter.
        """
        if not ctx.guild or not len(argument) > 1 or not argument[0] == "'":
            return await commands.CategoryChannelConverter().convert(ctx, argument)

        catid = find_aliased_category_id(ctx, argument)

        return await commands.CategoryChannelConverter().convert(ctx, str(catid))
