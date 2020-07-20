import json

import discord
from discord.ext import commands

from context import BlimpContext


class MaybeAliasedMessage(discord.Message):
    """An alias-aware converter for Messages."""

    @classmethod
    async def convert(cls, ctx: BlimpContext, argument: str):
        """
        Convert an alias to a message or fall back to the message converter.
        """
        if not ctx.guild or not len(argument) > 1 or not argument[0] == "'":
            return await commands.MessageConverter().convert(ctx, argument)

        row = ctx.bot.get_cog("Objects").alias_to_object(ctx.guild.id, argument)
        if not row:
            raise commands.BadArgument(f"Unknown alias {argument}.")

        data = json.loads(row["data"]).get("m")
        if not data:
            raise commands.BadArgument(f"Alias {argument} doesn't refer to a message.")

        return await commands.MessageConverter().convert(ctx, f"{data[0]}-{data[1]}")
