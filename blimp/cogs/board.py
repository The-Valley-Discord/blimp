import json
import re
import sqlite3
from datetime import datetime
from typing import List, Optional

import discord
from discord.ext import commands

from ..customizations import Blimp, UnableToComply, Unauthorized
from .alias import MaybeAliasedTextChannel


class Board(Blimp.Cog):
    "Building monuments to all your sins."

    @commands.group()
    async def board(self, ctx: Blimp.Context):
        """A Board is a channel that gets any messages that get enough of certain reactions reposted
        into it. Also known as "starboard" on other, sadly land-bound, bots."""

    @commands.command(parent=board)
    async def update(
        self,
        ctx: Blimp.Context,
        channel: MaybeAliasedTextChannel,
        emoji: str,
        min_reacts: int,
        post_age_limit: bool = False,
    ):
        """Update a Board, overwriting prior configuration.

        `emoji` is the reaction the Board listens to, it may be either a custom or built-in emoji,
        or "any". In the latter case, any emoji can trigger the Board.

        `min_reacts` is how many reactions of `emoji` you want a message to have before it triggers
        the Board.

        `post_age_limit` controls if posts older than the board configuration should be reposted, by
        default old posts are ignored."""

        if not ctx.privileged_modify(channel.guild):
            raise Unauthorized()

        emoji_id = re.search(r"(\d{10,})>?$", emoji)
        if emoji_id:
            emoji = int(emoji_id[1])

        age = None
        if post_age_limit:
            age = ctx.message.created_at

        logging_embed = discord.Embed(
            description=f"{ctx.author} updated Board {channel.mention}.",
            color=ctx.Color.I_GUESS,
        )

        old = ctx.database.execute(
            "SELECT * FROM board_configuration WHERE oid=:oid",
            {"oid": ctx.objects.by_data(tc=channel.id)},
        ).fetchone()
        if old:
            data = json.loads(old["data"])

            logging_embed.add_field(
                name="Old",
                value=f"Emoji: {ctx.bot.get_emoji(data[0]) or data[0]}\n"
                f"Minimum Reacts: {data[1]}\n"
                f"Limit to new posts: {old['post_age_limit'] is not None}",
            )

        ctx.database.execute(
            """INSERT OR REPLACE INTO board_configuration(oid, guild_oid, data, post_age_limit)
            VALUES(:oid, :guild_oid, :data, :age)""",
            {
                "oid": ctx.objects.make_object(tc=channel.id),
                "guild_oid": ctx.objects.make_object(g=channel.guild.id),
                "data": json.dumps([emoji, min_reacts]),
                "age": age,
            },
        )

        logging_embed.add_field(
            name="New",
            value=f"Emoji: {ctx.bot.get_emoji(emoji) or emoji}\n"
            f"Minimum Reacts: {min_reacts}\n"
            f"Limit to new posts: {post_age_limit}",
        )

        await ctx.bot.post_log(channel.guild, embed=logging_embed)

        await ctx.reply(f"*Overwrote board configuration for {channel.mention}.*")

    @commands.command(parent=board)
    async def disable(self, ctx: Blimp.Context, channel: MaybeAliasedTextChannel):
        "Disable a Board and delete its configuration."

        if not ctx.privileged_modify(channel.guild):
            raise Unauthorized()

        cursor = ctx.database.execute(
            """DELETE FROM board_configuration WHERE oid=:oid""",
            {"oid": ctx.objects.by_data(tc=channel.id)},
        )
        if cursor.rowcount == 0:
            raise UnableToComply(
                f"Can't disable Board in {channel.mention} as none exists."
            )

        await ctx.bot.post_log(
            channel.guild, f"{ctx.author} deleted board {channel.mention}."
        )

        await ctx.reply(f"*Deleted board configuration for {channel.mention}.*")

    @commands.command(parent=board)
    async def view(
        self, ctx: Blimp.Context, channel: Optional[MaybeAliasedTextChannel]
    ):
        """Display currently Board configuration of either one channel or all channels in this
        server.

        `channel` is the channel whose Board configuration to display. Can be left empty to list all
        active Boards in this server."""

        def format_data(row: sqlite3.Row) -> dict:
            "format a board_configuration row"
            data = json.loads(row["data"])
            channel = ctx.bot.get_channel(ctx.objects.by_oid(row["oid"])["tc"])
            return {
                "name": f"Board: #{channel}\n",
                "value": f"Emoji: {ctx.bot.get_emoji(data[0]) or data[0]}\n"
                f"Minimum Reacts: {data[1]}\n"
                f"Limit to new posts: {row['post_age_limit'] is not None}",
            }

        if channel:
            board_data = ctx.database.execute(
                "SELECT * FROM board_configuration WHERE oid=:oid",
                {"oid": ctx.objects.by_data(tc=channel.id)},
            ).fetchone()
            if not board_data:
                raise UnableToComply(f"{channel.mention} is not a Board.")

            await ctx.reply(
                embed=discord.Embed(color=ctx.Color.GOOD).add_field(
                    **format_data(board_data)
                )
            )

        else:
            rows = ctx.database.execute(
                "SELECT * FROM board_configuration WHERE guild_oid=:oid",
                {"oid": ctx.objects.by_data(g=ctx.guild.id)},
            ).fetchall()

            if not rows:
                await ctx.reply(
                    "There are no Boards are configured on this server.",
                    color=ctx.Color.I_GUESS,
                )
                return

            embed = discord.Embed(color=ctx.Color.GOOD)
            for row in rows:
                embed.add_field(**format_data(row))

            await ctx.reply(embed=embed)

    @staticmethod
    def format_message(
        msg: discord.Message, reactions: List[discord.Reaction]
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
            value=f"{reactions[0].count}x {' '.join([str(r) for r in reactions])}"
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
            if board[
                "post_age_limit"
            ] and orig_message.created_at < datetime.fromisoformat(
                board["post_age_limit"]
            ):
                return

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

            if not possible_reactions:
                continue

            max_count = max(possible_reactions, key=lambda react: react.count).count
            reaction = [
                react for react in possible_reactions if react.count == max_count
            ]

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
                await board_msg.edit(embed=self.format_message(orig_message, reaction))
            else:
                board_channel = self.bot.get_channel(objects.by_oid(board["oid"])["tc"])
                if (
                    orig_message.author == orig_channel.guild.me
                    and orig_channel == board_channel
                ):
                    continue

                board_msg = await board_channel.send(
                    "", embed=self.format_message(orig_message, reaction)
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
