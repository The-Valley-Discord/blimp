import random
from datetime import datetime, timedelta, timezone

import discord
from discord.ext import commands

from ..customizations import Blimp
from ..eff_large_wordlist import WORDS


class Malarkey(Blimp.Cog):
    "And you know why? Because life itself is filled with no reason."

    pings = ["Pong!", "Ping!", "DING!", "Pyongyang!", "PLONK", "Pink!"]

    @Blimp.Cog.listener()
    async def on_message(self, msg: discord.Message):
        "React to messages that ping the bot."
        if not msg.author == self.bot.user and self.bot.user in msg.mentions:
            await msg.add_reaction("❗")

    @commands.command()
    async def ping(self, ctx: Blimp.Context):
        "Find out if the bot's still alive. It's easier to just ping it."
        raise ValueError()
        now = datetime.now(timezone.utc)
        pong = random.choice(self.pings)
        in_delta = now - ctx.message.created_at
        msg = await ctx.reply(
            f"*{pong}*",
            subtitle=f"Inbound: {in_delta/timedelta(milliseconds=1)}ms",
        )
        out_delta = msg.created_at - now
        await msg.edit(
            embed=discord.Embed(
                color=ctx.Color.GOOD,
                description=f"*{pong}*",
            ).set_footer(
                text=f"Inbound: {in_delta/timedelta(milliseconds=1)}ms | "
                f"Outbound: {out_delta/timedelta(milliseconds=1)}ms"
            )
        )

    @commands.command()
    async def givemeafreegenderneutralname(self, ctx: Blimp.Context):
        """Get yourself a free and gender-neutral name.

        Words courtesy of the EFF."""

        amount = random.randint(2, 3)
        words = random.choices(WORDS, k=amount)

        await ctx.reply(
            "**I AUTHORISE AND REQUIRE** all persons at all times to designate, "
            f"describe, and address {ctx.author.mention} by the adopted free and gender-neutral "
            f"name of **{' '.join(words)}**."
        )

    @commands.command()
    async def choose(self, ctx: Blimp.Context, *options):
        """Choose a random option of those provided.

        `options` is a space-separated list of options."""

        await ctx.reply(f"Hmmm… I choose {random.choice(options)}!")
