from datetime import datetime, timedelta
import random

import discord
from discord.ext import commands

from customizations import Blimp


class Malarkey(Blimp.Cog):
    """*Silly things.*
    And you know why? Because life itself is filled with no reason."""

    pings = ["Pong!", "Ping!", "DING!", "Pyongyang!", "PLONK", "Pink!"]

    @Blimp.Cog.listener()
    async def on_message(self, msg: discord.Message):
        "React to messages that ping the bot."
        if self.bot.user in msg.mentions or msg.mention_everyone:
            await msg.add_reaction("❗")

    @commands.command()
    async def ping(self, ctx: Blimp.Context):
        "Find out if the bot's still alive. It's easier to just ping it."
        now = datetime.utcnow()
        pong = random.choice(self.pings)
        in_delta = now - ctx.message.created_at
        msg = await ctx.reply(
            f"*{pong}*", subtitle=f"Inbound: {in_delta/timedelta(milliseconds=1)}ms",
        )
        out_delta = msg.created_at - now
        await msg.edit(
            embed=discord.Embed(
                color=ctx.Color.GOOD, description=f"*{pong}*",
            ).set_footer(
                text=f"Inbound: {in_delta/timedelta(milliseconds=1)}ms | "
                f"Outbound: {out_delta/timedelta(milliseconds=1)}ms"
            )
        )
