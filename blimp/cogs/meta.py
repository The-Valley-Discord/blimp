from urllib.parse import quote

import discord
from discord.ext import commands

from ..customizations import Blimp, UnableToComply


class Meta(Blimp.Cog):
    "There is no such thing as bad PR."

    @commands.command()
    async def feedback(self, ctx: Blimp.Context, *, text: str):
        """Send feedback to the BLIMP development and support server. You can provide suggestions
        and bug reports this way without having to open issues. We'll try to reach out to you if
        we want additional clarification or your suggestion is accepted or rejected."""

        feedback_channel_id = ctx.bot.config["info"].get("feedback_id")
        if not feedback_channel_id:
            raise UnableToComply(
                "This instance of BLIMP doesn't have a configured feedback channel. "
                "Contact your operator."
            )

        feedback_channel = ctx.bot.get_channel(int(feedback_channel_id))

        embed = (
            discord.Embed(description=text, color=ctx.Color.I_GUESS)
            .set_author(
                name=f"{ctx.author} ({ctx.author.id})",
                icon_url=ctx.author.avatar_url,
            )
            .set_footer(
                text=f"in {ctx.guild.name} ({ctx.guild.id})" if ctx.guild else "in DMs",
                icon_url=ctx.guild.icon_url if ctx.guild else ctx.bot.user.avatar_url,
            )
        )

        if ctx.bot.config["info"]["source"].startswith("https://github.com"):
            url = (
                ctx.bot.config["info"]["source"]
                + "/issues/new"
                + "?title="
                + quote("Discord Feedback: …")
                + "&body="
                + quote(text)
                + quote(f"\n\nFeedback submitted by {ctx.author}.")
            )
            if not len(url) > 1000:
                embed.add_field(name="Create Issue", value=f"[→ GitHub]({url})")

        embed.add_field(
            name="Reply",
            value=f"post{ctx.bot.suffix} {ctx.channel.id} reference = {ctx.message.id}\n"
            + 'content = ""',
            inline=False,
        )

        await feedback_channel.send(embed=embed)

        await ctx.reply(
            "Thanks for your feedback! We'll do our best to keep you posted on the status of your "
            "suggestion."
        )
