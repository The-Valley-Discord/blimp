from datetime import timedelta
import tempfile
from typing import Optional

import discord
from discord.ext import commands

from .aliasing import MaybeAliasedCategoryChannel, MaybeAliasedTextChannel
from ..customizations import Blimp
from ..transcript import Transcript


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
            description=f"{ctx.author} updated ticket category {category.name}",
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
            ticket_categories(category_oid, guild_oid, count, transcript_channel_oid,
                per_user_limit, can_creator_close)

            VALUES(:category_oid, :guild_oid, :count, :transcript_channel_oid, :per_user_limit,
                :can_creator_close)""",
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

        await ctx.reply(f"Updated ticket category {category.name}.")

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
            description=f"{ctx.author} updated ticket class {category.name}/{name}",
            color=ctx.Color.I_GUESS,
        )

        old = ctx.database.execute(
            "SELECT * FROM ticket_classes WHERE category_oid=:category_oid and name=:name",
            {"category_oid": ctx.objects.by_data(cc=category.id), "name": name},
        ).fetchone()
        if old:
            log_embed.add_field(
                name="Old Description",
                value=description,
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
            name="New Description",
            value=description,
        )

        await self.bot.post_log(category.guild, embed=log_embed)

        await ctx.reply(f"Updated ticket class {category.name}/{name}.")

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

            await ctx.bot.post_log(
                ticket_channel.guild,
                f"{ctx.author} opened ticket {ticket_channel.name} [{ticket_channel.mention}].",
                color=ctx.Color.I_GUESS,
            )

        initial_message = await ticket_channel.send(
            ctx.author.mention,
            embed=discord.Embed(
                title=f"Welcome to {actual_class['name']}-{ticket_category['count'] + 1}!\n",
                description=(
                    "Staff "
                    + ("and you " if ticket_category["can_creator_close"] else "")
                    + f"can delete this ticket using :x: or `ticket{ctx.bot.suffix} delete`\n"
                    + "Add or remove participants using "
                    + f"`ticket{ctx.bot.suffix} add` and `ticket{ctx.bot.suffix} remove`.\n"
                ),
                color=ctx.Color.AUTOMATIC_BLUE,
            ).set_footer(text="BLIMP Tickets", icon_url=ctx.bot.user.avatar_url),
        )
        await initial_message.pin()
        await ticket_channel.purge(limit=1, check=lambda m: m.author == self.bot.user)
        await ticket_channel.send(actual_class["description"])
        ctx.database.execute(
            """INSERT INTO
            trigger_entries(message_oid, emoji, command)
            VALUES(:message_oid, :emoji, :command)""",
            {
                "message_oid": ctx.objects.make_object(
                    m=[initial_message.channel.id, initial_message.id]
                ),
                "emoji": "\N{CROSS MARK}",
                "command": f"ticket{self.bot.suffix} delete",
            },
        )
        await initial_message.add_reaction("\N{CROSS MARK}")

    @commands.command(parent=ticket)
    async def delete(
        self,
        ctx: Blimp.Context,
        channel: Optional[MaybeAliasedTextChannel],
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

        created_timestamp = channel.created_at - timedelta(
            microseconds=channel.created_at.microsecond
        )
        deleted_timestamp = ctx.message.created_at - timedelta(
            microseconds=ctx.message.created_at.microsecond
        )
        archive_embed = (
            discord.Embed(
                title=f"#{channel.name}",
                color=ctx.Color.I_GUESS,
            )
            .add_field(
                name="Created",
                value=str(created_timestamp) + f"\n<@{ticket['creator_id']}>",
            )
            .add_field(
                name="Deleted", value=str(deleted_timestamp) + "\n" + ctx.author.mention
            )
        )

        with tempfile.TemporaryFile(mode="r+") as temp:
            messages = await Transcript.write_transcript(temp, channel)
            temp.seek(0)

            participants = set([message.author for message in messages])
            archive_embed.add_field(
                name="Participants",
                value="\n".join(user.mention for user in participants),
            )

            await transcript_channel.send(
                embed=archive_embed,
                file=discord.File(fp=temp, filename=f"{channel.name}.html"),
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
            first_message = (
                await channel.history(limit=1, oldest_first=True).flatten()
            )[0]
            trans.execute(
                "DELETE FROM trigger_entries WHERE message_oid=:message_oid",
                {"message_oid": ctx.objects.by_data(m=[channel.id, first_message.id])},
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
                overwrites=overwrites_without_member,
                reason=str(ctx.author),
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