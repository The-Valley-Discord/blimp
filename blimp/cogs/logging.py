from discord.ext import commands

from ..customizations import Blimp, UnableToComply, Unauthorized
from .alias import MaybeAliasedTextChannel


class Logging(Blimp.Cog):
    "Watching with ten thousand eyes."

    @commands.group()
    async def logging(self, ctx: Blimp.Context):
        """Set up logging for your server to keep you informed on BLIMP's actions.

        Currently, logs are generated by **configuration changes** for logging, Boards, Kiosks,
        Slowmodes, Tickets, Triggers, and the Welcome and Goodbye logs. Additional logs are
        generated for individual **ticket creation and deletion**, as well as ticket **add/remove
        events**. **Channel bans** and unbans also are logged, as are changes to **channel
        names/topics** made through BLIMP."""

    @commands.command(parent=logging, name="set")
    async def _set(self, ctx: Blimp.Context, channel: MaybeAliasedTextChannel):
        "Set the logging channel."
        if not ctx.privileged_modify(channel.guild):
            raise Unauthorized()

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

        await ctx.reply(f"New logs will be posted in {channel.mention}.")

    @commands.command(parent=logging)
    async def disable(self, ctx: Blimp.Context):
        "Disable logging and delete existing configuration."
        if not ctx.privileged_modify(ctx.guild):
            raise Unauthorized()

        old = ctx.database.execute(
            "SELECT * FROM logging_configuration WHERE guild_oid =:guild_oid",
            {
                "guild_oid": ctx.objects.make_object(g=ctx.guild.id),
            },
        ).fetchone()
        if not old:
            raise UnableToComply("Logging is not enabled in this server.")

        await ctx.bot.post_log(
            ctx.guild,
            f"{ctx.author} disabled logging.",
            color=ctx.Color.I_GUESS,
        )

        ctx.database.execute(
            "DELETE FROM logging_configuration WHERE guild_oid =:guild_oid",
            {
                "guild_oid": ctx.objects.make_object(g=ctx.guild.id),
            },
        )

        await ctx.reply("Disabled logging.")

    @commands.command(parent=logging)
    async def view(self, ctx: Blimp.Context):
        "View the logging channel."

        row = ctx.database.execute(
            "SELECT * FROM logging_configuration WHERE guild_oid=:guild_oid",
            {
                "guild_oid": ctx.objects.make_object(g=ctx.guild.id),
            },
        ).fetchone()

        if row:
            channel = ctx.objects.by_oid(row["channel_oid"])["tc"]
            await ctx.reply(f"The current logging channel is <#{channel}>.")
        else:
            await ctx.reply(
                "There is no logging channel configured on this server.",
                color=ctx.Color.I_GUESS,
            )
