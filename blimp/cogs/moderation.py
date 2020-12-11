from typing import Optional

import discord
from discord.ext import commands

from ..customizations import Blimp, UnableToComply, Unauthorized
from .alias import MaybeAliasedTextChannel


class Moderation(Blimp.Cog):
    "*Suppressing your free speech since 1724.*"

    @commands.command()
    async def channelban(
        self,
        ctx: Blimp.Context,
        channel: Optional[MaybeAliasedTextChannel],
        member: discord.Member,
        *,
        reason: str,
    ):
        """Ban a member from writing or reacting in a channel. They'll still be able to read.

        `channel` is the channel to ban from. If left empty, BLIMP works with the current channel.

        `member` is the member to channel-ban.

        `reason` is the reason for the ban. It's mandatory."""

        if not channel:
            channel = ctx.channel

        if not ctx.privileged_modify(channel):
            raise Unauthorized()

        if member == ctx.author:
            raise UnableToComply("You can't channelban yourself.")

        if member == ctx.bot.user:
            raise UnableToComply("No.")

        exists = ctx.database.execute(
            "SELECT * FROM channelban_entries WHERE channel_oid=:c_oid AND user_oid=:u_oid",
            {
                "c_oid": ctx.objects.make_object(tc=channel.id),
                "u_oid": ctx.objects.make_object(u=member.id),
            },
        ).fetchone()

        if exists:
            raise UnableToComply("Member is already channelbanned.")

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
            member, send_messages=False, add_reactions=False, reason=str(ctx.author)
        )

        await ctx.bot.post_log(
            channel.guild,
            f"{ctx.author} channel-banned {member.mention} from {channel.mention}:\n> {reason}",
        )
        await ctx.reply(f"*Channel-banned {member.mention}.*")

    @commands.command()
    async def unchannelban(
        self,
        ctx: Blimp.Context,
        channel: Optional[MaybeAliasedTextChannel],
        member: discord.Member,
    ):
        """Lift a channelban from a member.

        `channel` is the channel to unban from. If left empty, BLIMP works with the current channel.

        `member` is the member to lift the channel-ban from."""

        if not channel:
            channel = ctx.channel

        if not ctx.privileged_modify(channel):
            return

        exists = ctx.database.execute(
            "SELECT * FROM channelban_entries WHERE channel_oid=:c_oid AND user_oid=:u_oid",
            {
                "c_oid": ctx.objects.make_object(tc=channel.id),
                "u_oid": ctx.objects.make_object(u=member.id),
            },
        ).fetchone()

        if not exists:
            raise UnableToComply("Member is not channel-banned.")

        ctx.database.execute(
            "DELETE FROM channelban_entries WHERE channel_oid=:c_oid AND user_oid=:u_oid",
            {
                "c_oid": ctx.objects.by_data(tc=channel.id),
                "u_oid": ctx.objects.by_data(u=member.id),
            },
        )

        await channel.set_permissions(member, send_messages=None, add_reactions=None)

        await ctx.bot.post_log(
            channel.guild,
            f"{ctx.author} lifted the channelban on {member.mention} in {channel.mention}",
        )
        await ctx.reply(f"*Lifted the channel-ban on {member.mention}.*")

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
                await channel.set_permissions(
                    member, send_messages=False, add_reactions=False
                )
                log_str += f"{channel.mention} OK\n"
            except:  # pylint: disable=bare-except
                channel_id = self.bot.objects.by_oid(row["channel_oid"])["tc"]
                log_str += f"<#{channel_id}> Error, auto-unbanning.\n"
                self.bot.database.execute(
                    "DELETE FROM channelban_entries WHERE user_oid=:u_oid AND channel_oid=:c_oid",
                    {
                        "u_oid": row["user_oid"],
                        "c_oid": row["channel_oid"],
                    },
                )

        log_embed = discord.Embed(
            color=self.bot.Context.Color.AUTOMATIC_BLUE,
            description=f"Reapplying channelbans to re-joined {member.mention}",
        ).add_field(name="Channels", value=log_str)

        await self.bot.post_log(member.guild, embed=log_embed)
