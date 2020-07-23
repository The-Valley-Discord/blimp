import json
from string import Template

import discord
from discord.ext import commands

from customizations import Blimp
from .alias import MaybeAliasedTextChannel


class Welcome(Blimp.Cog):
    """*Greeting and goodbye-ing people.*
    Welcome and Goodbye allow you to greet and see off users that join/leave
    your server. The messages allow you to mention the user in question, but
    don't offer a lot of detail a proper logging bot would provide, mostly
    because that's a different use case."""

    @commands.group()
    async def welcome(self, ctx: Blimp.Context):
        "Configure user-facing join notifications."

    @commands.command(parent=welcome, name="update")
    async def w_update(
        self, ctx: Blimp.Context, channel: MaybeAliasedTextChannel, *, greeting: str
    ):
        """Update user-facing join messages for this server.
        
        `channel` designates where the messages will be posted.
        In `greeting`, $user is replaced with a mention of the user joining."""
        if not ctx.privileged_modify(channel.guild):
            return

        ctx.database.execute(
            """INSERT INTO welcome_configuration(oid, join_data) VALUES(:oid, json(:data))
            ON CONFLICT(oid) DO UPDATE SET join_data=excluded.join_data""",
            {
                "oid": ctx.objects.make_object(g=channel.guild.id),
                "data": json.dumps([ctx.objects.make_object(tc=channel.id), greeting]),
            },
        )
        await ctx.reply("*Overwrote welcome configuration, example message follows.*")
        await ctx.send(
            Template(greeting).safe_substitute({"user": channel.guild.me.mention})
        )

    @commands.command(parent=welcome, name="disable")
    async def w_disable(self, ctx: Blimp.Context):
        "Disable the server's welcome messages and delete stored data."
        if not ctx.privileged_modify(ctx.guild):
            return
        cursor = ctx.database.execute(
            "UPDATE welcome_configuration SET join_data=NULL WHERE oid=:oid",
            {"oid": ctx.objects.make_object(g=ctx.guild.id)},
        )
        if cursor.rowcount == 0:
            await ctx.reply(
                """*I, yet again tasked*
                *to erase what doesn't exist,*
                *quietly ignore.*""",
                subtitle="Welcome is not enabled for this server.",
                color=ctx.Color.I_GUESS,
            )
            return

        await ctx.reply("*Deleted welcome configuration.*")

    @Blimp.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        """
        Look up if we have a configuration for this guild and greet if so.
        """
        objects = self.bot.objects

        cursor = self.bot.database.execute(
            "SELECT * FROM welcome_configuration WHERE oid=:oid",
            {"oid": objects.by_data(g=member.guild.id)},
        )
        row = cursor.fetchone()
        if not row or not row["join_data"]:
            return

        data = json.loads(row["join_data"])
        channel = self.bot.get_channel(objects.by_oid(data[0])["tc"])

        await channel.send(Template(data[1]).safe_substitute({"user": member.mention}))

    @commands.group()
    async def goodbye(self, ctx: Blimp.Context):
        "Configure user-facing leave notifications."

    @commands.command(parent=goodbye, name="update")
    async def g_update(
        self, ctx: Blimp.Context, channel: MaybeAliasedTextChannel, *, greeting: str
    ):
        """Update user-facing leave messages for this server.
        
        `channel` designates where the messages will be posted.
        In `greeting`, $user is replaced with a mention of the user leaving."""
        if not ctx.privileged_modify(channel.guild):
            return

        ctx.database.execute(
            """INSERT INTO welcome_configuration(oid, leave_data) VALUES(:oid, json(:data))
            ON CONFLICT(oid) DO UPDATE SET leave_data=excluded.leave_data""",
            {
                "oid": ctx.objects.make_object(g=channel.guild.id),
                "data": json.dumps([ctx.objects.make_object(tc=channel.id), greeting]),
            },
        )
        await ctx.reply("*Overwrote goodbye configuration, example message follows.*")
        await ctx.send(
            Template(greeting).safe_substitute({"user": channel.guild.me.mention})
        )

    @commands.command(parent=goodbye, name="disable")
    async def g_disable(self, ctx: Blimp.Context):
        "Disable the server's goodbye messages and delete stored data."
        if not ctx.privileged_modify(ctx.guild):
            return
        cursor = ctx.database.execute(
            "UPDATE welcome_configuration SET leave_data=NULL WHERE oid=:oid",
            {"oid": ctx.objects.make_object(g=ctx.guild.id)},
        )
        if cursor.rowcount == 0:
            await ctx.reply(
                """*heartbroken, ordered*
                *to remove a farewell, joy*
                *as I can refuse.*""",
                subtitle="Goodbye is not enabled for this server.",
                color=ctx.Color.I_GUESS,
            )
            return

        await ctx.reply("*Deleted goodbye configuration.*")

    @Blimp.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        "Look up if we have a configuration for this guild and say goodbye if so."
        objects = self.bot.objects

        cursor = self.bot.database.execute(
            "SELECT * FROM welcome_configuration WHERE oid=:oid",
            {"oid": objects.by_data(g=member.guild.id)},
        )
        row = cursor.fetchone()
        if not row or not row["leave_data"]:
            return

        data = json.loads(row["leave_data"])
        channel = self.bot.get_channel(objects.by_oid(data[0])["tc"])

        await channel.send(Template(data[1]).safe_substitute({"user": member.mention}))
