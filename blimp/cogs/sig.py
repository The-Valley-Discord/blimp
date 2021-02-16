import sqlite3
from typing import Optional

from discord.ext import commands

from ..customizations import Blimp, Unauthorized
from .alias import MaybeAliasedTextChannel


class SIG(Blimp.Cog):
    "Like roles, but worse."

    @commands.group()
    async def sig(self, ctx: Blimp.Context):
        """SIGs allow channel moderators to notify active members of their channels, on an opt-in
        basis, without needing Manage Roles permission or using up role slots."""

    @commands.command(parent=sig)
    async def view(self, ctx: Blimp.Context):
        "View which SIGs you are subscribed to."

        sigs = ctx.database.execute(
            "SELECT channel_oid FROM sig_entries WHERE user_id = :user_id",
            {"user_id": ctx.author.id},
        ).fetchall()
        if not sigs:
            await ctx.reply(
                "You aren't subscribed to any SIGs.", color=ctx.Color.I_GUESS
            )
            return

        await ctx.reply(
            "You are subscribed to these SIGs:\n"
            + "\n".join(
                [
                    await ctx.bot.represent_object(ctx.objects.by_oid(channel_oid))
                    for (channel_oid,) in sigs
                ]
            )
        )

    @commands.command(parent=sig)
    async def join(
        self, ctx: Blimp.Context, channels: commands.Greedy[MaybeAliasedTextChannel]
    ):
        """Join one or multiple SIGs, signing up for notifications from them.

        `channels` are the channels whose SIGs you would like to join. If left empty, BLIMP works
        with the current channel."""

        if not channels:
            channels = [ctx.channel]

        for channel in channels:
            if not channel.permissions_for(ctx.author).read_messages:
                raise Unauthorized()
                
            try:
                ctx.database.execute(
                    "INSERT INTO sig_entries(channel_oid, user_id) VALUES(:channel_oid, :user_id)",
                    {
                        "channel_oid": ctx.objects.make_object(tc=channel.id),
                        "user_id": ctx.author.id,
                    },
                )
                await ctx.reply(f"Subscribed to the SIG for {channel.mention}.")
            except sqlite3.IntegrityError:
                await ctx.reply(
                    f"You are already subscribed to the SIG for {channel.mention}.",
                    color=ctx.Color.I_GUESS,
                )

    @commands.command(parent=sig)
    async def leave(
        self, ctx: Blimp.Context, channels: commands.Greedy[MaybeAliasedTextChannel]
    ):
        """Leave one or multiple SIGs, to stop getting notifications from them.

        `channels` are the channels whose SIGs you would like to leave. If left empty, BLIMP works
        with the current channel."""

        if not channels:
            channels = [ctx.channel]

        for channel in channels:
            old = ctx.database.execute(
                "SELECT * FROM sig_entries WHERE user_id = :user_id AND channel_oid=:channel_oid",
                {
                    "user_id": ctx.author.id,
                    "channel_oid": ctx.objects.make_object(tc=channel.id),
                },
            ).fetchone()

            if not old:
                await ctx.reply(
                    f"You weren't subscribed to the SIG for {channel.mention}.",
                    color=ctx.Color.I_GUESS,
                )
                return

            ctx.database.execute(
                "DELETE FROM sig_entries WHERE channel_oid=:channel_oid AND user_id=:user_id",
                {
                    "channel_oid": ctx.objects.make_object(tc=channel.id),
                    "user_id": ctx.author.id,
                },
            )
            await ctx.reply(f"Unsubscribed from the SIG for {channel.mention}.")

    @commands.command(parent=sig)
    async def ping(
        self, ctx: Blimp.Context, channel: Optional[MaybeAliasedTextChannel]
    ):
        """Ping all members of the SIG for a channel you moderate.

        `channel` is the channel you want to notify SIG members of. If left empty, BLIMP works with
        the current channel."""

        if not channel:
            channel = ctx.channel

        if not ctx.privileged_modify(channel):
            raise Unauthorized()

        members = ctx.database.execute(
            "SELECT user_id FROM sig_entries WHERE channel_oid = :channel_oid",
            {"channel_oid": ctx.objects.by_data(tc=channel.id)},
        ).fetchall()

        await ctx.reply(
            f"Pinging {len(members)} {channel.mention} SIG subscribers for {ctx.author}…"
        )

        pings = [f"<@{member}>" for (member,) in members]
        blocks = [""]
        for mention in pings:
            if len(mention) + len(blocks[-1]) < 1996:
                blocks[-1] += mention + " "
            else:
                blocks.append(mention)

        for block in blocks:
            await ctx.send(f"||{block.strip()}||")
