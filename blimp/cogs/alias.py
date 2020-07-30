import sqlite3
from typing import Union

import discord
from discord.ext import commands

from customizations import Blimp


class Aliasing(Blimp.Cog):
    """*Giving names to things.*
    Aliases allow you to refer to channels and messages (more targets to come)
    using simple, server-specific codes like `'rules` or `'the_bread_message`,
    that way you don't need to remember unwieldly Discord IDs."""

    @staticmethod
    def validate_alias(string) -> None:
        """Check if something should be allowed to be an alias."""
        if len(string) < 2 or string[0] != "'":
            raise commands.UserInputError(
                "Aliases must start with ' and have at least one character after that."
            )
        if len([ch for ch in string if ch.isspace()]) > 0:
            raise commands.UserInputError("Aliases may not contain whitespace.")

    @commands.group()
    async def alias(self, ctx: Blimp.Context):
        """
        Aliases for things so you don't always have to grab their ID
        """

    @commands.command(parent=alias)
    async def make(
        self,
        ctx: Blimp.Context,
        target: Union[discord.Message, discord.TextChannel, discord.CategoryChannel],
        alias: str,
    ):
        """
        Create an alias for a Discord object (messages, channels, categories).
        Aliases must start with a single ', have no whitespace, and be unique.
        """
        if not ctx.privileged_modify(ctx.guild):
            return

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
        except sqlite3.DatabaseError:
            ctx.database.execute("ABORT;")
            await ctx.reply(
                "*that word seems common*\n"
                "*for it's an alias.*\n"
                "*no doubles allowed.*",
                subtitle=f"{alias} is already registered as an alias.",
                color=ctx.Color.I_GUESS,
            )
            return

        ctx.database.execute("COMMIT;")

        link = await ctx.bot.represent_object(ctx.objects.by_oid(oid))
        await ctx.reply(f"*{link} is now known as {alias}.*")

    @commands.command(parent=alias)
    async def delete(self, ctx: Blimp.Context, alias: str):
        "Delete an alias, freeing it up for renewed use."

        if not ctx.privileged_modify(ctx.guild):
            return

        self.validate_alias(alias)

        old = ctx.objects.by_alias(ctx.guild.id, alias)
        if not old:
            await ctx.reply(
                "*commonly you ask*\n"
                "*to delete extant objects*\n"
                "*though not this time.*",
                subject="Unknown alias.",
                color=ctx.Color.I_GUESS,
            )
            return

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
            await ctx.reply(
                "*honest yet verbose,*\n"
                "*no aliases 'round here.*\n"
                "*maybe you'll change that?*",
                subtitle="No aliases configured for this server.",
                color=ctx.Color.I_GUESS,
            )
            return

        await ctx.reply(result)


class MaybeAliasedMessage(discord.Message):
    """An alias-aware converter for Messages."""

    @classmethod
    async def convert(cls, ctx: Blimp.Context, argument: str):
        """
        Convert an alias to a message or fall back to the message converter.
        """
        if not ctx.guild or not len(argument) > 1 or not argument[0] == "'":
            return await commands.MessageConverter().convert(ctx, argument)

        oid, data = ctx.objects.by_alias(ctx.guild.id, argument)
        if not oid:
            raise commands.BadArgument(f"Unknown alias {argument}.")

        if not data.get("m"):
            raise commands.BadArgument(f"Alias {argument} doesn't refer to a message.")

        return await commands.MessageConverter().convert(
            ctx, f"{data['m'][0]}-{data['m'][1]}"
        )


class MaybeAliasedTextChannel(discord.TextChannel):
    """An alias-aware converter for TextChannels."""

    @classmethod
    async def convert(cls, ctx: Blimp.Context, argument: str):
        """
        Convert an alias to a channel or fall back to the TextChannel converter.
        """
        if not ctx.guild or not len(argument) > 1 or not argument[0] == "'":
            return await commands.TextChannelConverter().convert(ctx, argument)

        oid, data = ctx.objects.by_alias(ctx.guild.id, argument)
        if not oid:
            raise commands.BadArgument(f"Unknown alias {argument}.")

        if not data.get("tc"):
            raise commands.BadArgument(
                f"Alias {argument} doesn't refer to a text channel."
            )

        return await commands.TextChannelConverter().convert(ctx, str(data["tc"]))


class MaybeAliasedCategoryChannel(discord.CategoryChannel):
    """An alias-aware converter for CategoryChannels."""

    @classmethod
    async def convert(cls, ctx: Blimp.Context, argument: str):
        """
        Convert an alias to a channel or fall back to the CategoryChannel converter.
        """
        if not ctx.guild or not len(argument) > 1 or not argument[0] == "'":
            return await commands.CategoryChannelConverter().convert(ctx, argument)

        oid, data = ctx.objects.by_alias(ctx.guild.id, argument)
        if not oid:
            raise commands.BadArgument(f"Unknown alias {argument}.")

        if not data.get("cc"):
            raise commands.BadArgument(f"Alias {argument} doesn't refer to a category.")

        return await commands.CategoryChannelConverter().convert(ctx, str(data["cc"]))
