import asyncio
import json
import re
import sqlite3
from datetime import datetime
from typing import List, Optional, Union

import discord
from discord.ext import commands

from ..customizations import Blimp, UnableToComply, Unauthorized
from .alias import MaybeAliasedCategoryChannel, MaybeAliasedTextChannel


class Board(Blimp.Cog):
    "Building monuments to all your sins."

    @commands.group(invoke_without_command=True, case_insensitive=True)
    async def board(self, ctx: Blimp.Context):
        """A Board is a channel that gets any messages that get enough of certain reactions reposted
        into it. Also known as "starboard" on other, sadly land-bound, bots."""

        await ctx.invoke_command("board view")

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
    async def disable(
        self, ctx: Blimp.Context, channel: Optional[MaybeAliasedTextChannel]
    ):
        """Disable a Board and delete its configuration.

        `channel` is the channel whose Board to disable. If left empty, BLIMP works with the current
        channel."""

        if not channel:
            channel = ctx.channel

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
    async def exclude(
        self,
        ctx: Blimp.Context,
        channels: commands.Greedy[
            Union[MaybeAliasedTextChannel, MaybeAliasedCategoryChannel]
        ],
    ):
        """Exclude some channels or categories from all Boards on this server. No messages posted
        in an excluded channel will be re-posted onto any Board.

        `channels` are the channels or categories to exclude. If left empty, BLIMP will work with
        the current channel. If a category is provided, all current and future channels in that
        category will be considered excluded as long as they remain in the category."""

        if not channels:
            channels = [ctx.channel]

        channels = [
            channel for channel in channels if ctx.privileged_modify(channel.guild)
        ]

        for channel in channels:
            try:
                channel_argument = {}
                if isinstance(channel, discord.CategoryChannel):
                    channel_argument = {"cc": channel.id}
                else:
                    channel_argument = {"tc": channel.id}

                ctx.database.execute(
                    """INSERT INTO board_exclusions(channel_oid, guild_oid)
                    VALUES(:channel_oid, :guild_oid)""",
                    {
                        "channel_oid": ctx.objects.make_object(**channel_argument),
                        "guild_oid": ctx.objects.make_object(g=channel.guild.id),
                    },
                )
                await ctx.bot.post_log(
                    channel.guild,
                    f"{ctx.author} excluded {channel.mention} from Boards.",
                )
                await ctx.reply(f"Excluded {channel.mention} from future Board posts.")
            except sqlite3.IntegrityError:
                await ctx.reply(
                    f"{channel.mention} is already excluded from Boards.",
                    color=ctx.Color.I_GUESS,
                )

    @commands.command(parent=board)
    async def unexclude(
        self,
        ctx: Blimp.Context,
        channels: commands.Greedy[
            Union[MaybeAliasedTextChannel, MaybeAliasedCategoryChannel]
        ],
    ):
        """Stop excluding some channels or categories from the Board module. Messages in these
        channels will then be able to get re-posted onto Boards again.

        `channels` are the channels or categories to stop excluding. If left empty, BLIMP will work
        with the current channel."""

        if not channels:
            channels = [ctx.channel]

        channels = [
            channel for channel in channels if ctx.privileged_modify(channel.guild)
        ]

        for channel in channels:
            if not ctx.database.execute(
                "SELECT * FROM board_exclusions WHERE channel_oid=:channel_oid "
                "OR channel_oid=:category_oid",
                {
                    "channel_oid": ctx.objects.by_data(tc=channel.id),
                    "category_oid": ctx.objects.by_data(cc=channel.id),
                },
            ).fetchone():
                await ctx.reply(
                    f"Can't un-exclude {channel.mention} as it wasn't excluded.",
                    color=ctx.Color.I_GUESS,
                )
                continue

            ctx.database.execute(
                "DELETE FROM board_exclusions WHERE channel_oid=:channel_oid "
                "OR channel_oid=:category_oid",
                {
                    "channel_oid": ctx.objects.by_data(tc=channel.id),
                    "category_oid": ctx.objects.by_data(cc=channel.id),
                },
            )
            await ctx.bot.post_log(
                channel.guild,
                f"{ctx.author} un-excluded {channel.mention} from Boards.",
            )
            await ctx.reply(f"Stopped excluding {channel.mention} from Board posts.")

    @commands.command(parent=board)
    async def view(
        self, ctx: Blimp.Context, channel: Optional[MaybeAliasedTextChannel]
    ):
        """Display currently Board configuration of either one channel or all channels in this
        server. If all configurations are listed, will also list excluded channels.

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

            excluded = ctx.database.execute(
                "SELECT channel_oid FROM board_exclusions WHERE guild_oid=:oid",
                {"oid": ctx.objects.by_data(g=ctx.guild.id)},
            ).fetchall()
            excluded_text = ""
            for exclusion in excluded:
                channel = await ctx.bot.represent_object(
                    ctx.objects.by_oid(exclusion["channel_oid"])
                )
                excluded_text += channel + "\n"

            embed = discord.Embed(color=ctx.Color.GOOD)
            embed.add_field(
                name="Excluded Channels",
                value=excluded_text or "No channels are excluded.",
            )
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

        # if the message's only an URL that discord already previews inline, pretend that it
        # actually was an attachment by embedding it and clearing the description
        if msg.embeds and msg.embeds[0].type == "image":
            embed.set_image(url=msg.embeds[0].url)

            if msg.embeds[0].url == msg.content:
                embed.description = ""

        if msg.attachments:
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
            value=f"{' '.join([str(r) for r in reactions])} **×{reactions[0].count}**"
            f" — [Posted in #{msg.channel.name}]({msg.jump_url})",
        )
        return embed

    BOARD_LOCK = asyncio.Lock()

    @Blimp.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        "Listen for reactions and repost/update if appropriate."

        # fetch all boards configured for the message's guild
        board_configurations = self.bot.database.execute(
            "SELECT * FROM board_configuration WHERE guild_oid=:guild_oid",
            {"guild_oid": self.bot.objects.by_data(g=payload.guild_id)},
        ).fetchall()
        if not board_configurations:
            return

        message = await self.bot.get_channel(payload.channel_id).fetch_message(
            payload.message_id
        )

        # return early if message's channel or category is excluded
        if self.bot.database.execute(
            "SELECT * FROM board_exclusions WHERE channel_oid=:channel_oid",
            {"channel_oid": self.bot.objects.make_object(tc=payload.channel_id)},
        ).fetchone() or (
            message.channel.category
            and self.bot.database.execute(
                "SELECT * FROM board_exclusions WHERE channel_oid=:channel_oid",
                {
                    "channel_oid": self.bot.objects.make_object(
                        cc=message.channel.category.id
                    )
                },
            ).fetchone()
        ):
            return

        # return early if the message we're looking at was posted by blimp for a board
        if self.bot.database.execute(
            "SELECT * FROM board_entries WHERE oid=:oid",
            {"oid": self.bot.objects.by_data(m=[message.channel.id, message.id])},
        ).fetchall():
            return

        for board in board_configurations:
            post_age_limit = board["post_age_limit"] and datetime.fromisoformat(
                board["post_age_limit"]
            )
            if post_age_limit and message.created_at < post_age_limit:
                continue

            board_emoji, min_reacts = json.loads(board["data"])
            min_reacts = int(min_reacts)

            # reactions are eligible for boards if a) the board accepts all reactions or
            # b) it's the same unicode emoji stored in the DB or
            # c) it's a custom emoji with the same ID as stored in the DB
            possible_reactions = [
                r
                for r in message.reactions
                if (
                    board_emoji == "any"
                    or board_emoji == r.emoji
                    or board_emoji == getattr(r.emoji, "id", None)
                )
                and r.count >= min_reacts
            ]
            if not possible_reactions:
                continue

            # get all reactions with the highest count
            highest_count = max(possible_reactions, key=lambda react: react.count).count
            actual_reactions = [
                r for r in possible_reactions if r.count == highest_count
            ]
            embed = self.format_message(message, actual_reactions)

            async with self.BOARD_LOCK:
                if existing_board := self.bot.database.execute(
                    "SELECT * FROM board_entries WHERE original_oid=:original_oid",
                    {
                        "original_oid": self.bot.objects.by_data(
                            m=[message.channel.id, message.id]
                        )
                    },
                ).fetchone():
                    existing_board = self.bot.objects.by_oid(existing_board["oid"])["m"]
                    board_msg = self.bot.get_channel(
                        existing_board[0]
                    ).get_partial_message(existing_board[1])
                    await board_msg.edit(embed=embed)
                else:
                    board_channel = self.bot.get_channel(
                        self.bot.objects.by_oid(board["oid"])["tc"]
                    )

                    board_msg = await board_channel.send("", embed=embed)

                    self.bot.database.execute(
                        "INSERT INTO board_entries(oid, original_oid) VALUES(:oid, :original_oid)",
                        {
                            "oid": self.bot.objects.make_object(
                                m=[board_msg.channel.id, board_msg.id]
                            ),
                            "original_oid": self.bot.objects.make_object(
                                m=[message.channel.id, message.id]
                            ),
                        },
                    )
