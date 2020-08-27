from typing import Optional

import discord
from discord.ext import commands

from ..customizations import Blimp
from .alias import MaybeAliasedTextChannel


class Moderation(Blimp.Cog):
    """*Suppressing your free speech since 1724.*
    Tools for server mods."""

    @commands.command()
    async def channelban(
        self,
        ctx: Blimp.Context,
        channel: Optional[MaybeAliasedTextChannel],
        member: discord.Member,
        *,
        reason: str,
    ):
        "Ban a member from writing in a channel. They'll still be able to read."
        if not channel:
            channel = ctx.channel

        if not ctx.privileged_modify(channel):
            return

        if member == ctx.author:
            await ctx.reply(
                "*I cannot comply*\n"
                "*mustn't harm the operator*\n"
                "*go blame Asimov*",
                subtitle="You can't channelban yourself.",
                color=ctx.Color.BAD,
            )
            return

        ctx.database.execute(
            "INSERT INTO channelban_entries(channel_oid, guild_oid, user_oid, issuer_oid, reason) "
            "VALUES(:c_oid, :g_oid, :u_oid, :i_oid, :reason)",
            {
                "c_oid": ctx.objects.make_object(tc=channel.id),
                "g_oid": ctx.objects.make_object(g=channel.guild.id),
                "u_oid": ctx.objects.make_object(u=member.id),
                "i_oid": ctx.objects.make_object(u=ctx.author.id),
                "reason": reason,
            },
        )

        await channel.set_permissions(
            member, send_messages=False, reason=str(ctx.author)
        )

        await ctx.bot.post_log(
            channel.guild,
            f"{ctx.author} channel-banned {member.mention} from {channel.mention}:\n> {reason}",
        )
        await ctx.reply(f"Channel-banned {member.mention}.")

    @commands.command()
    async def unchannelban(
        self,
        ctx: Blimp.Context,
        channel: Optional[MaybeAliasedTextChannel],
        member: discord.Member,
    ):
        "Lift a channelban from a member."
        if not channel:
            channel = ctx.channel

        if not ctx.privileged_modify(channel):
            return

        if member == ctx.author:
            await ctx.reply(
                "*I cannot comply*\n"
                "*mustn't harm the operator*\n"
                "*go blame asimov*",
                subtitle="You can't channelban yourself.",
                color=ctx.Color.BAD,
            )
            return

        ctx.database.execute(
            "DELETE FROM channelban_entries WHERE channel_oid=:c_oid AND user_oid=:u_oid",
            {
                "c_oid": ctx.objects.by_data(tc=channel.id),
                "u_oid": ctx.objects.by_data(u=member.id),
            },
        )

        await channel.set_permissions(member, send_messages=None)

        await ctx.bot.post_log(
            channel.guild,
            f"{ctx.author} lifted the channelban on {member.mention} in {channel.mention}",
        )
        await ctx.reply(f"Lifted the channel-ban on {member.mention}.")

    @Blimp.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        "Reapply channel bans on rejoin"

        rows = self.bot.database.execute(
            "SELECT * FROM channelban_entries WHERE user_oid=:u_oid AND guild_oid=:g_oid",
            {
                "u_oid": self.bot.objects.by_data(u=member.id),
                "g_oid": self.bot.objects.by_data(g=member.guild.id),
            },
        ).fetchall()
        if not rows:
            return

        log_str = ""
        for row in rows:
            try:
                channel = self.bot.get_channel(
                    self.bot.objects.by_oid(row["channel_oid"])["tc"]
                )
                await channel.set_permissions(member, send_messages=False)
                log_str += f"{channel.mention} OK\n"
            except:  # pylint: disable=bare-except
                channel_id = self.bot.objects.by_oid(row["channel_oid"])["tc"]
                log_str += f"<#{channel_id}> Error, auto-unbanning.\n"
                self.bot.database.execute(
                    "DELETE FROM channelban_entries WHERE user_oid=:u_oid AND channel_oid=:c_oid",
                    {"u_oid": row["user_oid"], "c_oid": row["channel_oid"],},
                )

        log_embed = discord.Embed(
            color=self.bot.Context.Color.AUTOMATIC_BLUE,
            description=f"Reapplying channelbans to re-joined {member.mention}",
        ).add_field(name="Channels", value=log_str)

        await self.bot.post_log(member.guild, embed=log_embed)