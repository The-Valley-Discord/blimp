from datetime import datetime, timedelta
from typing import Optional

import discord
from discord.ext import commands

from ..customizations import Blimp, ParseableTimedelta, Unauthorized
from .alias import MaybeAliasedTextChannel


class Slowmode(Blimp.Cog):
    "Deleting things that are just too new for your taste."

    @commands.group()
    async def slowmode(self, ctx: Blimp.Context):
        """BLIMP Slowmode is an extension of Discord's built-in slowmode, with arbitrary length for
        the slowmode. Once set up in a channel, BLIMP monitors all message timestamps and deletes
        messages that were posted to recently, notifying the user in question via DM."""

    @commands.command(parent=slowmode, name="set")
    async def _set(
        self,
        ctx: Blimp.Context,
        channel: Optional[MaybeAliasedTextChannel],
        duration: ParseableTimedelta,
        ignore_mods: bool = True,
    ):
        """Set a channel's slowmode to an arbitrary value.

        `channel` is the channel to target, if left empty, BLIMP works with the current channel.

        `duration` is a [duration]($manual#arguments). If over 6 hours, the bot will manually
        enforce slowmode by deleting messages that have been posted too soon since the last one. Set
        to a zero duration to disable slowmode.

        `ignore_mods` determines if BLIMP will delete messages from mods too. By default, it won't.
        """
        if not channel:
            channel = ctx.channel

        if not ctx.privileged_modify(channel):
            raise Unauthorized()

        secs = duration.total_seconds()
        await channel.edit(slowmode_delay=min(21600, secs), reason=str(ctx.author))

        ctx.database.execute(
            """INSERT OR REPLACE INTO
            slowmode_configuration(channel_oid, secs, ignore_privileged_users)
            VALUES(:oid, :secs, :ignore_privileged_users)""",
            {
                "oid": ctx.objects.make_object(tc=channel.id),
                "secs": secs,
                "ignore_privileged_users": ignore_mods,
            },
        )

        await ctx.bot.post_log(
            channel.guild,
            f"{ctx.author} set slowmode in {channel.mention} to {duration},"
            f"{' not' if not ignore_mods else ''} ignoring moderators.",
        )
        await ctx.reply(
            f"Set slowmode in {channel.mention} to {duration},"
            f"{' not' if not ignore_mods else ''} ignoring moderators."
        )

    @commands.command(parent=slowmode)
    async def clear(
        self,
        ctx: Blimp.Context,
        channel: Optional[MaybeAliasedTextChannel],
        user: discord.Member,
    ):
        """Reset a user's slowmode data, so they can post again immediately.

        `channel` is the channel to target, if left empty, BLIMP works with the current channel.

        `user` is the server member whose timestamp should be reset."""

        if not channel:
            channel = ctx.channel

        if not ctx.privileged_modify(channel):
            raise Unauthorized()

        ctx.database.execute(
            "DELETE FROM slowmode_entries WHERE channel_oid=:channel_oid AND user_oid=:user_oid",
            {
                "channel_oid": ctx.objects.by_data(tc=channel.id),
                "user_oid": ctx.objects.by_data(u=user.id),
            },
        )
        await ctx.reply(f"Deleted stored timestamp for {user} in {channel.mention}.")

    @Blimp.Cog.listener()
    async def on_message(self, msg: discord.Message):
        "Handle slowmode enforcement"
        channel_config = self.bot.database.execute(
            "SELECT * FROM slowmode_configuration WHERE channel_oid=:oid",
            {"oid": self.bot.objects.by_data(tc=msg.channel.id)},
        ).fetchone()
        if not channel_config:
            return

        if msg.author.bot:
            return

        last_message = self.bot.database.execute(
            "SELECT * FROM slowmode_entries WHERE channel_oid=:channel_oid AND user_oid=:user_oid",
            {
                "channel_oid": self.bot.objects.by_data(tc=msg.channel.id),
                "user_oid": self.bot.objects.by_data(u=msg.author.id),
            },
        ).fetchone()

        if not last_message or (
            msg.created_at - datetime.fromisoformat(last_message["timestamp"])
            > timedelta(seconds=channel_config["secs"])
        ):
            self.bot.database.execute(
                """INSERT OR REPLACE INTO slowmode_entries(channel_oid, user_oid, timestamp)
                VALUES(:channel_oid, :user_oid, :timestamp)""",
                {
                    "channel_oid": self.bot.objects.make_object(tc=msg.channel.id),
                    "user_oid": self.bot.objects.make_object(u=msg.author.id),
                    "timestamp": msg.created_at,
                },
            )

        else:
            if channel_config["ignore_privileged_users"] and (
                await self.bot.get_context(msg, cls=Blimp.Context)
            ).privileged_modify(msg.channel):
                return

            await msg.delete()

            remaining = timedelta(seconds=channel_config["secs"]) - (
                msg.created_at - datetime.fromisoformat(last_message["timestamp"])
            )
            remaining = remaining - timedelta(microseconds=remaining.microseconds)
            await msg.author.send(
                None,
                embed=discord.Embed(
                    title=f"Your message in #{msg.channel} was deleted by BLIMP Slowmode",
                    description=msg.content,
                    color=self.bot.Context.Color.AUTOMATIC_BLUE,
                    timestamp=msg.created_at,
                ).set_footer(text=f"{remaining} remaining"),
            )
