import asyncio

import discord
from discord.ext import commands

from customizations import Blimp, ParseableTimedelta
from .alias import MaybeAliasedCategoryChannel


class Tools(Blimp.Cog):
    """*Semi-useful things, actually.*
    This is a collection of commands that relate to everyday management
    and aren't significant enough to warrant their own module."""

    @commands.command()
    async def cleanup(self, ctx: Blimp.Context, limit: int = 20, any_bot: bool = False):
        """Go through the last messages and delete bot responses.

        `limit` controls the amount of messages searched, the default is 20.
        If `any_bot` is provided, will clear messages by any bot and not
        just BLIMP's."""
        if not ctx.privileged_modify(ctx.channel):
            return

        async with ctx.typing():
            purged = await ctx.channel.purge(
                limit=limit,
                check=lambda msg: msg.author == ctx.bot.user
                or (any_bot and msg.author.bot),
            )

        info = await ctx.reply(
            f"*Deleted {len(purged)} of {limit} messages. "
            "This message will self-destruct in five seconds.*"
        )
        await asyncio.sleep(5.0)
        await info.delete()

    @commands.command()
    async def stalechannels(
        self,
        ctx: Blimp.Context,
        category: MaybeAliasedCategoryChannel,
        duration: ParseableTimedelta = ParseableTimedelta(days=2),
    ):
        "List channels in a category that have been stale for a certain duration."
        channels = []
        for channel in category.channels:
            if (
                not isinstance(channel, discord.TextChannel)
                or not channel.last_message_id
            ):
                continue

            timestamp = discord.utils.snowflake_time(channel.last_message_id)
            delta = ctx.message.created_at - timestamp

            # chop off ms
            delta = delta - ParseableTimedelta(microseconds=delta.microseconds)
            if delta > duration:
                channels.append((channel, delta))

        await ctx.reply(
            "\n".join(
                [f"{channel.mention} {delta} ago" for channel, delta in channels]
            ),
            subtitle=f"Channels in {category.name} that haven't been used in {duration}",
        )

    @commands.command()
    @commands.is_owner()
    async def eval(self, ctx: Blimp.Context, *, code: str):
        "Evaluate an expression as a lambda."
        the_letter_after_kappa = eval(code)  # pylint: disable=eval-used
        await the_letter_after_kappa(ctx)
        await ctx.message.add_reaction("\N{WHITE HEAVY CHECK MARK}")

    @commands.command()
    async def pleasetellmehowmanypeoplehave(
        self, ctx: Blimp.Context, role: discord.Role
    ):
        members = [m for m in ctx.guild.members if role in m.roles]
        await ctx.reply(f"{len(members)} members have {role.mention}.")
