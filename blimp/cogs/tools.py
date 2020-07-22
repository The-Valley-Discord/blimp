import asyncio

from discord.ext import commands

from customizations import Blimp


class Tools(Blimp.Cog):
    """
    Semi-useful things, actually.
    """

    @commands.command()
    async def cleanup(self, ctx: Blimp.Context, limit: int = 20, any_bot: bool = False):
        """Go through the last messages and delete bot responses.

        <limit> controls the amount of messages searched, the default is 20.

        If <any_bot> is enabled, will clear messages by any bot and not
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
