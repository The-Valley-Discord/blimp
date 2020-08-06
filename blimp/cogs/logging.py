from discord.ext import commands

from ..customizations import Blimp
from .alias import MaybeAliasedTextChannel


class Logging(Blimp.Cog):
    """*Watching with ten thousand eyes.*
    Set up logging for your server to keep you informed on BLIMP actions."""

    @commands.group()
    async def logging(self, ctx: Blimp.Context):
        "Configure logging"

    @commands.command(parent=logging, name="set")
    async def _set(self, ctx: Blimp.Context, channel: MaybeAliasedTextChannel):
        "Set the logging channel."
        if not ctx.privileged_modify(channel.guild):
            return

        await ctx.bot.post_log(
            channel.guild,
            f"{ctx.author} updated logging channel to {channel.mention}.",
            color=ctx.Color.I_GUESS,
        )

        ctx.database.execute(
            """INSERT OR REPLACE INTO logging_configuration(guild_oid, channel_oid)
            VALUES(:guild_oid, :channel_oid)""",
            {
                "channel_oid": ctx.objects.make_object(tc=channel.id),
                "guild_oid": ctx.objects.make_object(g=channel.guild.id),
            },
        )

        await ctx.reply(f"*New logs will be posted in {channel.mention}.*")
