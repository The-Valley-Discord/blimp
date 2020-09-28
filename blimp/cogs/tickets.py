from datetime import timedelta
import html
import re
from string import Template
import tempfile
from typing import Optional

import discord
from discord.ext import commands

from ..customizations import Blimp
from .alias import MaybeAliasedCategoryChannel, MaybeAliasedTextChannel


def shrink(string):
    "Remove whitespace from a string"
    return re.sub(r"\n\s*", "", string)


class Transcript:
    "Just a place to chuck all of the transcript related code so it can get collapsed in VSC"

    @staticmethod
    def fancify_content(content):
        "Faithfully recreate discord's markup in HTML. absolutely disgusting"
        content = html.escape(content)

        def emojify(match):
            return (
                f"<img src='https://cdn.discordapp.com/emojis/{match[3]}"
                + (".gif" if match[1] == "a" else ".png")
                + f"' class='emoji' title='{match[2]}'>"
            )

        content = re.sub(r"&lt;(a?):(\w+):(\d+)&gt;", emojify, content)

        content = re.sub(r"```(.+)```", r"<pre>\1</pre>", content, flags=re.DOTALL)
        # advanced[tm] markdown processing
        content = content.replace("\n", "<br>")
        content = re.sub(r"\*\*([^\*]+)\*\*", r"<b>\1</b>", content)
        content = re.sub(r"\*([^\*]+)\*", r"<i>\1</i>", content)
        content = re.sub(r"~~([^~]+)~~", r"<del>\1</del>", content)
        content = re.sub(r"`([^`]+)`", r"<code>\1</code>", content)
        if content == "":
            content = "<span class='no-content'>No content.</span>"
        return content

    TRANSCRIPT_HEADER = Template(
        shrink(
            """
            <!doctype html>
            <html>
            <head>
                <meta charset="utf-8">
                <title>#$channelname</title>
                <style>
                    body {
                        background: #36393f;
                        color: #dcddde;
                        font-family: Roboto, sans-serif;
                    }
                    .message-container {
                        margin: 1rem 0;
                        display: grid;
                        grid-template-columns: 3rem auto;
                        grid-template-rows: 1.3rem auto;
                        grid-column-gap: 1rem;
                        border-left: 3px solid #36393f;
                        padding-left: 5px;
                        min-height: 2.6rem;
                    }
                    .message-container .metadata {
                        grid-column: 2;
                        grid-row: 1;
                    }
                    .message-container .metadata *, .message-container .content .no-content {
                        color: #72767d;
                        font-size: .8rem;
                    }
                    .message-container .metadata .author {
                        font-size: 1rem;
                        color: #dcddde;
                        margin-right: .3rem;
                        font-weight: bold;
                    }
                    .message-container .metadata .id-anchor {
                        text-decoration: none;
                    }
                    .message-container .metadata .id-anchor:hover {
                        text-decoration: underline;
                    }
                    .message-container img.avatar {
                        grid-column: 1;
                        width: 3rem;
                        border-radius: 50%;
                    }
                    .message-container .content {
                        max-width: 75ch;
                        overflow-wrap: anywhere;
                        line-height: 1.3rem;
                        grid-column: 2;
                    }
                    .content a {
                        color: #00b0f4;
                    }
                    .content pre, content code {
                        font-size: .8rem;
                        background: #2f3136;
                        padding: .3rem;
                        overflow-wrap: anywhere;
                        font-family: monospace;
                    }
                    .content img.emoji {
                        height: 1.3rem;
                        vertical-align: middle;
                    }
                    .content img.emoji.emoji-big {
                        height: 2.6rem;
                    }
                    .content img.attachment {
                        display: block;
                        max-width: 32em;
                    }
                </style>
            </head>
            <body>
                <h3>$headline</h3>
                <div id="messagelog">
            """
        )
    )

    TRANSCRIPT_ITEM = Template(
        shrink(
            """
            <div class="message-container" id="$messageid">
                <img class="avatar" src="$authoravatar">
                <div class="metadata">
                    <span class="author" title="$authortag">$authornick </span>
                    <span class="timestamp">$timestamp </span>
                    <a href="#$messageid" class="id-anchor">$messageid</a>
                </div>
                <div class="content">$content</div>
            </div>
            """
        )
    )

    TRANSCRIPT_FOOTER = "</div></body></html>"

    @classmethod
    async def write_transcript(cls, file, channel):
        "Write a transcript of the channel into file."
        file.write(
            cls.TRANSCRIPT_HEADER.substitute(
                channelname=channel.name,
                headline=f"#{channel.name} on {channel.guild.name}",
            )
        )
        async for message in channel.history(limit=None, oldest_first=True):
            clean_timestamp = message.created_at - timedelta(
                microseconds=message.created_at.microsecond
            )
            file.write(
                cls.TRANSCRIPT_ITEM.substitute(
                    messageid=message.id,
                    authortag=str(message.author),
                    authornick=message.author.display_name,
                    authoravatar=message.author.avatar_url,
                    timestamp=clean_timestamp,
                    content=cls.fancify_content(message.clean_content)
                    + "\n".join(
                        [
                            f"<img src='{a.url}' class='attachment' title='{a.filename}'>"
                            for a in message.attachments
                        ]
                    ),
                )
            )
        file.write(cls.TRANSCRIPT_FOOTER)


class Tickets(Blimp.Cog):
    """*Honorary citizen #23687, please! Don't push.*
    Tickets allow users to create temporary channels to, for example, request assistance, talk to
    moderators privately, or organize internal discussions."""

    @commands.group()
    async def ticket(self, ctx: Blimp.Context):
        "Manage individual tickets and overall ticket configuration."

    @commands.command(parent=ticket)
    async def updatecategory(
        self,
        ctx: Blimp.Context,
        category: MaybeAliasedCategoryChannel,
        last_ticket_number: int,
        transcript_channel: MaybeAliasedTextChannel,
        can_creator_close: bool,
        per_user_limit: Optional[int],
    ):
        "Update a Ticket category, overwriting its setup entirely."

        if not ctx.privileged_modify(category.guild):
            return

        log_embed = discord.Embed(
            description=f"{ctx.author} updated ticket category {category.mention}",
            color=ctx.Color.I_GUESS,
        )

        old = ctx.database.execute(
            "SELECT * FROM ticket_categories WHERE category_oid=:category_oid",
            {"category_oid": ctx.objects.by_data(cc=category.id)},
        ).fetchone()
        if old:
            transcript_obj = ctx.objects.by_oid(old["transcript_channel_oid"])
            log_embed.add_field(
                name="Old",
                value=f"Last Ticket: {old['count']}\n"
                f"Transcripts: {await self.bot.represent_object(transcript_obj)}\n"
                f"Creators can close/delete: {old['can_creator_close']}\n"
                f"Per-User Limit: {old['per_user_limit']}",
            )

        ctx.database.execute(
            """INSERT OR REPLACE INTO
        ticket_categories(category_oid, guild_oid, count, transcript_channel_oid, per_user_limit, can_creator_close)
        VALUES(:category_oid, :guild_oid, :count, :transcript_channel_oid, :per_user_limit, :can_creator_close)""",
            {
                "category_oid": ctx.objects.make_object(cc=category.id),
                "guild_oid": ctx.objects.make_object(g=category.guild.id),
                "count": last_ticket_number,
                "transcript_channel_oid": ctx.objects.make_object(
                    tc=transcript_channel.id
                ),
                "per_user_limit": per_user_limit,
                "can_creator_close": can_creator_close,
            },
        )

        log_embed.add_field(
            name="New",
            value=f"Last Ticket: {last_ticket_number}\n"
            f"Transcripts: {transcript_channel.mention}\n"
            f"Creators can close/delete: {can_creator_close}\n"
            f"Per-User Limit: {per_user_limit}",
        )

        await self.bot.post_log(category.guild, embed=log_embed)

        await ctx.reply(f"Updated ticket category {category.mention}.")

    @commands.command(parent=ticket)
    async def updateclass(
        self,
        ctx: Blimp.Context,
        category: MaybeAliasedCategoryChannel,
        name: str,
        *,
        description: str,
    ):
        "Update a Ticket class, overwriting its setup entirely."

        if not ctx.privileged_modify(category.guild):
            return

        log_embed = discord.Embed(
            description=f"{ctx.author} updated ticket class {category.mention}/{name}",
            color=ctx.Color.I_GUESS,
        )

        old = ctx.database.execute(
            "SELECT * FROM ticket_classes WHERE category_oid=:category_oid and name=:name",
            {"category_oid": ctx.objects.by_data(cc=category.id), "name": name},
        ).fetchone()
        if old:
            log_embed.add_field(
                name="Old Description", value=description,
            )

        ctx.database.execute(
            """INSERT OR REPLACE INTO
        ticket_classes(category_oid, name, description)
        VALUES(:category_oid, :name, :description)""",
            {
                "category_oid": ctx.objects.make_object(cc=category.id),
                "name": name,
                "description": description,
            },
        )

        log_embed.add_field(
            name="New Description", value=description,
        )

        await self.bot.post_log(category.guild, embed=log_embed)

        await ctx.reply(f"Updated ticket class {category.mention}/{name}.")

    @commands.command(parent=ticket, name="open")
    async def _open(
        self,
        ctx: Blimp.Context,
        category: MaybeAliasedCategoryChannel,
        ticket_class: Optional[str],
    ):
        """Open a new ticket in the specified category.

        [ticket_class] can be left out if only one class exists in that category."""

        with ctx.database as trans:
            ticket_category = trans.execute(
                "SELECT * FROM ticket_categories WHERE category_oid=:category_oid",
                {"category_oid": ctx.objects.by_data(cc=category.id)},
            ).fetchone()
            if not ticket_category:
                return

            actual_class = None
            ticket_classes = trans.execute(
                "SELECT * FROM ticket_classes WHERE category_oid=:category_oid",
                {"category_oid": ctx.objects.by_data(cc=category.id)},
            ).fetchall()
            if len(ticket_classes) == 1:
                actual_class = ticket_classes[0]
            else:
                actual_class_candidates = [
                    cl for cl in ticket_classes if cl["name"] == ticket_class
                ]
                if len(actual_class_candidates) != 1:
                    return

                actual_class = actual_class_candidates[0]

            if ticket_category["per_user_limit"] and not ctx.privileged_modify(
                category
            ):
                count = trans.execute(
                    """SELECT count(*) FROM ticket_entries WHERE
                    creator_id=:creator_id AND category_oid=:category_oid""",
                    {
                        "creator_id": ctx.author.id,
                        "category_oid": ctx.objects.by_data(cc=category.id),
                    },
                ).fetchone()
                if count[0] >= ticket_category["per_user_limit"]:
                    await ctx.reply(
                        f"you can't have more than {ticket_category['per_user_limit']} tickets",
                        color=ctx.Color.BAD,
                    )
                    return

            ticket_channel = await category.create_text_channel(
                f"{actual_class['name']}-{(ticket_category['count'] + 1)}",
                reason=f"Ticket in {category.name} for {ctx.author}",
                overwrites={
                    **category.overwrites,
                    ctx.author: discord.PermissionOverwrite(
                        read_messages=True, send_messages=True
                    ),
                },
            )

            trans.execute(
                "UPDATE ticket_categories SET count=:count WHERE category_oid=:category_oid",
                {
                    "count": ticket_category["count"] + 1,
                    "category_oid": ticket_category["category_oid"],
                },
            )

            trans.execute(
                """INSERT INTO ticket_entries(channel_oid, category_oid, creator_id, open)
            VALUES(:channel_oid, :category_oid, :creator_id, 1)""",
                {
                    "category_oid": ticket_category["category_oid"],
                    "channel_oid": ctx.objects.make_object(tc=ticket_channel.id),
                    "creator_id": ctx.author.id,
                },
            )

            trans.execute(
                """INSERT INTO ticket_participants(channel_oid, user_id)
                VALUES(:channel_oid, :user_id)""",
                {
                    "channel_oid": ctx.objects.make_object(tc=ticket_channel.id),
                    "user_id": ctx.author.id,
                },
            )

        initial_message = await ticket_channel.send(
            ctx.author.mention,
            embed=discord.Embed(
                description="this is a ticket", color=ctx.Color.AUTOMATIC_BLUE
            ),
        )
        await initial_message.pin()
        await ticket_channel.purge(limit=1, check=lambda m: m.author == self.bot.user)
        await ticket_channel.send(actual_class["description"])

    @commands.command(parent=ticket)
    async def delete(
        self, ctx: Blimp.Context, channel: Optional[MaybeAliasedTextChannel],
    ):
        """Delete a ticket and post a transcript."""

        if not channel:
            channel = ctx.channel

        ticket = ctx.database.execute(
            "SELECT * FROM ticket_entries WHERE channel_oid = :channel_oid",
            {"channel_oid": ctx.objects.by_data(tc=channel.id)},
        ).fetchone()
        if not ticket:
            return

        category = ctx.database.execute(
            "SELECT * from ticket_categories WHERE category_oid=:category_oid",
            {"category_oid": ticket["category_oid"]},
        ).fetchone()

        if not (
            ctx.privileged_modify(channel)
            or (category["can_creator_close"] and ctx.author.id == ticket["creator_id"])
        ):
            return

        await ctx.reply("Saving transcript…")
        transcript_channel_obj = ctx.objects.by_oid(category["transcript_channel_oid"])
        transcript_channel = self.bot.get_channel(transcript_channel_obj["tc"])

        with tempfile.TemporaryFile(mode="r+") as temp:
            await Transcript.write_transcript(temp, channel)
            temp.seek(0)

            await transcript_channel.send(
                None, file=discord.File(fp=temp, filename=f"{channel.name}.html")
            )

        with ctx.database as trans:
            trans.execute(
                "DELETE FROM ticket_participants WHERE channel_oid = :channel_oid",
                {"channel_oid": ctx.objects.by_data(tc=channel.id)},
            )
            trans.execute(
                "DELETE FROM ticket_entries WHERE channel_oid = :channel_oid",
                {"channel_oid": ctx.objects.by_data(tc=channel.id)},
            )

            await channel.delete()
            await ctx.bot.post_log(
                channel.guild,
                f"{ctx.author} deleted ticket {channel.name} [{channel.mention}].",
                color=ctx.Color.I_GUESS,
            )

    @commands.command(parent=ticket)
    async def add(
        self,
        ctx: Blimp.Context,
        channel: Optional[MaybeAliasedTextChannel],
        members: commands.Greedy[discord.Member],
    ):
        "Add members to a ticket."
        if not channel:
            channel = ctx.channel

        ticket = ctx.database.execute(
            "SELECT * FROM ticket_entries WHERE channel_oid = :channel_oid",
            {"channel_oid": ctx.objects.by_data(tc=channel.id)},
        ).fetchone()
        if not ticket:
            return

        if not (
            ctx.privileged_modify(channel) or ctx.author.id == ticket["creator_id"]
        ):
            return

        member_text = " ".join([member.mention for member in members])
        await ctx.bot.post_log(
            channel.guild,
            f"{ctx.author} added {member_text} to ticket {channel.name} [{channel.mention}]",
            color=ctx.Color.I_GUESS,
        )

        for member in members:
            await channel.edit(
                overwrites={
                    **channel.overwrites,
                    member: discord.PermissionOverwrite(read_messages=True),
                },
                reason=str(ctx.author),
            )
            ctx.database.execute(
                """INSERT INTO ticket_participants(channel_oid, user_id)
                VALUES(:channel_oid, :user_id)""",
                {
                    "channel_oid": ctx.objects.make_object(tc=channel.id),
                    "user_id": member.id,
                },
            )
            await ctx.reply(f"Added {member.mention}.")

    @commands.command(parent=ticket)
    async def remove(
        self,
        ctx: Blimp.Context,
        channel: Optional[MaybeAliasedTextChannel],
        members: commands.Greedy[discord.Member],
    ):
        "Remove members from a ticket."
        if not channel:
            channel = ctx.channel

        ticket = ctx.database.execute(
            "SELECT * FROM ticket_entries WHERE channel_oid = :channel_oid",
            {"channel_oid": ctx.objects.by_data(tc=channel.id)},
        ).fetchone()
        if not ticket:
            return

        if not (
            ctx.privileged_modify(channel) or ctx.author.id == ticket["creator_id"]
        ):
            return

        member_text = " ".join([member.mention for member in members])
        await ctx.bot.post_log(
            channel.guild,
            f"{ctx.author} removed {member_text} from ticket {channel.name} [{channel.mention}]",
            color=ctx.Color.I_GUESS,
        )

        for member in members:
            overwrites_without_member = channel.overwrites
            overwrites_without_member.pop(member, None)
            await channel.edit(
                overwrites=overwrites_without_member, reason=str(ctx.author),
            )
            ctx.database.execute(
                """DELETE FROM ticket_participants WHERE channel_oid = :channel_oid
                AND user_id = :user_id""",
                {
                    "channel_oid": ctx.objects.make_object(tc=channel.id),
                    "user_id": member.id,
                },
            )
            await ctx.reply(f"Removed {member.mention}.")

    @Blimp.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        "Look up if we have the member leave any tickets behind."

        tickets = self.bot.database.execute(
            """
            SELECT ticket_entries.channel_oid, ticket_entries.category_oid
            FROM ticket_participants
            LEFT JOIN ticket_entries ON ticket_participants.channel_oid = ticket_entries.channel_oid
            WHERE user_id=:user_id
            """,
            {"user_id": member.id},
        )
        for ticket in tickets:
            category_obj = self.bot.objects.by_oid(ticket["category_oid"])
            if not self.bot.get_channel(category_obj["cc"]).guild == member.guild:
                continue

            channel_obj = self.bot.objects.by_oid(ticket["channel_oid"])
            channel = self.bot.get_channel(channel_obj["tc"])
            await Blimp.Context.reply(
                channel, f"{member.mention} left.", color=Blimp.Context.Color.I_GUESS
            )

    @Blimp.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        "Look up if the member was in any tickets."

        tickets = self.bot.database.execute(
            """
            SELECT ticket_entries.channel_oid, ticket_entries.category_oid
            FROM ticket_participants
            LEFT JOIN ticket_entries ON ticket_participants.channel_oid = ticket_entries.channel_oid
            WHERE user_id=:user_id
            """,
            {"user_id": member.id},
        )
        for ticket in tickets:
            category_obj = self.bot.objects.by_oid(ticket["category_oid"])
            if not self.bot.get_channel(category_obj["cc"]).guild == member.guild:
                continue

            channel_obj = self.bot.objects.by_oid(ticket["channel_oid"])
            channel = self.bot.get_channel(channel_obj["tc"])
            await Blimp.Context.reply(
                channel,
                f"Added {member.mention} after rejoin.",
                color=Blimp.Context.Color.AUTOMATIC_BLUE,
            )
            await channel.edit(
                overwrites={
                    **channel.overwrites,
                    member: discord.PermissionOverwrite(read_messages=True),
                },
                reason="added to ticket on rejoin",
            )

