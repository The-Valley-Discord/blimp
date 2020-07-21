import json

import discord
from discord.ext import commands

from customizations import Blimp
from .alias import MaybeAliasedTextChannel


class Board(Blimp.Cog):
    """
    Putting up monuments to all your sins.
    """

    @commands.group()
    async def board(self, ctx: Blimp.Context):
        """
        The Board is a channel that gets any messages that get enough
        of certain reactions reposted into it. Also known as "starboard" on
        other, merely land-bound, bots.
        """

    @commands.command(parent=board)
    async def update(
        self,
        ctx: Blimp.Context,
        channel: MaybeAliasedTextChannel,
        emoji: str,
        min_reacts: str,
    ):
        """
        Update a Board, overwriting prior configuration.
        <emoji> may be any custom or built-in emoji or a literal "any",
        in which case the repost will trigger for any emoji.
        <min_reacts> is how many emoji you want the messages to have before
        they get reposted.
        """

        if not ctx.privileged_modify(channel.guild):
            return

        emoji_id = [ch for ch in emoji if ch.isdigit()]
        if len(emoji_id) != 0:
            emoji = int("".join(emoji_id))

        ctx.database.execute(
            """INSERT OR REPLACE INTO board_configuration(oid, guild_oid, data)
            VALUES(:oid, :guild_oid, :data)""",
            {
                "oid": ctx.objects.make_object(tc=channel.id),
                "guild_oid": ctx.objects.make_object(g=channel.guild.id),
                "data": json.dumps([emoji, min_reacts]),
            },
        )

        await ctx.reply(f"*Overwrote board configuration for {channel.mention}.*")

    @commands.command(parent=board)
    async def disable(self, ctx: Blimp.Context, channel: MaybeAliasedTextChannel):
        "Disable a Board, deleting prior configuration."

        if not ctx.privileged_modify(channel.guild):
            return

        cursor = ctx.database.execute(
            """DELETE FROM board_configuration WHERE oid=:oid""",
            {"oid": ctx.objects.by_data(tc=channel.id)},
        )
        if cursor.rowcount == 0:
            await ctx.reply(
                """*although unthought yet,*
                *more frivolous than a Board*
                *may be its absence.*""",
                subtitle="No Board is configured in that channel.",
                color=ctx.Color.I_GUESS,
            )
            return

        await ctx.reply(f"*Deleted board configuration for {channel.mention}.*")

    def format_message(
        self, msg: discord.Message, reaction: discord.Reaction
    ) -> discord.Embed:
        "Turn a message into an embed for the Board."

        embed = discord.Embed(
            description=msg.content,
            timestamp=msg.created_at,
            color=Blimp.Context.Color.AUTOMATIC_BLUE,
        )
        embed.set_author(name=msg.author, icon_url=msg.author.avatar_url)

        if len(msg.attachments) > 0:
            if msg.attachments[0].height:
                embed.set_image(url=msg.attachments[0].url)
            else:
                embed.add_field(
                    name="Attachment",
                    value=f"[{msg.attachments[0].filename}]({msg.attachments[0].url})",
                    inline=False,
                )

        embed.add_field(
            name="Message",
            value=f"{reaction.count}x {reaction}"
            f" — Posted to {msg.channel.mention} — "
            f"[Jump]({msg.jump_url})",
        )
        return embed

    @Blimp.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        "Listen for reactions and repost/update if appropriate."

        objects = self.bot.objects

        boards = self.bot.database.execute(
            "SELECT * FROM board_configuration WHERE guild_oid=:guild_oid",
            {"guild_oid": objects.by_data(g=payload.guild_id)},
        ).fetchall()
        if not boards:
            return

        orig_channel = self.bot.get_channel(payload.channel_id)
        orig_message = await orig_channel.fetch_message(payload.message_id)

        for board in boards:
            emoji, min_reacts = json.loads(board["data"])
            min_reacts = int(min_reacts)
            possible_reactions = [
                react
                for react in orig_message.reactions
                if (
                    emoji == "any"
                    or emoji == react.emoji
                    or emoji == getattr(react.emoji, "id", None)
                )
                and react.count >= min_reacts
            ]
            reaction = sorted(
                possible_reactions, key=lambda react: react.count, reverse=True,
            )
            if not reaction:
                continue

            to_edit = self.bot.database.execute(
                "SELECT * FROM board_entries WHERE original_oid=:original_oid",
                {
                    "original_oid": objects.by_data(
                        m=[orig_message.channel.id, orig_message.id]
                    )
                },
            ).fetchone()
            if to_edit:
                to_edit = objects.by_oid(to_edit["oid"])["m"]
                board_msg = await self.bot.get_channel(to_edit[0]).fetch_message(
                    to_edit[1]
                )
                await board_msg.edit(
                    embed=self.format_message(orig_message, reaction[0])
                )
            else:
                board_channel = self.bot.get_channel(objects.by_oid(board["oid"])["tc"])
                if (
                    orig_message.author == orig_channel.guild.me
                    and orig_channel == board_channel
                ):
                    continue

                board_msg = await board_channel.send(
                    "", embed=self.format_message(orig_message, reaction[0])
                )
                self.bot.database.execute(
                    "INSERT INTO board_entries(oid, original_oid) VALUES(:oid, :original_oid)",
                    {
                        "oid": objects.make_object(m=[board_channel.id, board_msg.id]),
                        "original_oid": objects.make_object(
                            m=[orig_channel.id, orig_message.id]
                        ),
                    },
                )
