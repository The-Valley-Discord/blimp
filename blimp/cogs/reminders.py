from datetime import datetime, timedelta
from typing import Union

import discord
from discord.ext import commands, tasks

from customizations import Blimp, ParseableDatetime, ParseableTimedelta


class Reminders(Blimp.Cog):
    """
    Reminding you of things that you believe are going to happen.
    """

    def __init__(self, *args):
        self.execute_reminders.start()  # pylint: disable=no-member
        super().__init__(*args)

    @tasks.loop(seconds=0.5)
    async def execute_reminders(self):
        "Look at overdue reminders and send notifications out."
        cursor = self.bot.database.execute(
            "SELECT * FROM reminders_entries WHERE due < strftime('%Y-%m-%dT%H:%M:%S', 'now')"
        )
        cursor.arraysize = 5
        entries = cursor.fetchmany()
        for entry in entries:
            invoke_msg = self.bot.objects.by_oid(entry["message_oid"])["m"]
            channel = None

            try:
                channel = self.bot.get_user(entry["user_id"])
                channel = self.bot.get_channel(invoke_msg[0])
            except:  # pylint: disable=bare-except
                pass
            finally:
                self.bot.database.execute(
                    "DELETE FROM reminders_entries WHERE id=:id", {"id": entry["id"]},
                )

            await channel.send(
                self.bot.get_user(entry["user_id"]).mention,
                embed=discord.Embed(
                    description=f"*Reminder:* {entry['text']}",
                ).add_field(
                    name="Context",
                    value=f"{await self.bot.represent_object({'m':invoke_msg})} "
                    f"from {discord.utils.snowflake_time(invoke_msg[1])}",
                ),
            )

    @commands.group()
    async def reminders(self, ctx: Blimp.Context):
        "Manage timed reminders."

    @commands.command(parent=reminders, name="list")
    async def _list(self, ctx: Blimp.Context):
        "List all pending reminders for you."
        rems = ctx.database.execute(
            "SELECT * FROM reminders_entries WHERE user_id=:user_id",
            {"user_id": ctx.author.id},
        ).fetchall()

        if not rems:
            await ctx.reply(
                "*here? nothing. bleak, yet*\n"
                "*lacking future's burdens*\n"
                "*maybe you are free.*",
                subtitle="You have no pending reminders.",
                color=ctx.Color.I_GUESS,
            )
            return

        rows = []
        for rem in rems:
            invoke_msg = ctx.objects.by_oid(rem["message_oid"])
            invoke_link = await self.bot.represent_object(invoke_msg)
            rows.append(f"`{rem['id']}` {rem['text']} ({rem['due']}, {invoke_link})")

        await ctx.reply("\n".join(rows))

    @commands.command(parent=reminders)
    async def delete(self, ctx: Blimp.Context, _id: int):
        "Delete one of your reminders."

        old = ctx.database.execute(
            "SELECT * FROM reminders_entries WHERE user_id=:user_id AND id=:id",
            {"user_id": ctx.author.id, "id": _id},
        ).fetchone()
        if not old:
            await ctx.reply(
                "*set to erase one*\n"
                "*I poured through all records*\n"
                "*yet the hunt proved fruitless.*",
                subtitle="Error: Unknown reminder ID.",
                color=ctx.Color.I_GUESS,
            )
            return

        ctx.database.execute(
            "DELETE FROM reminders_entries WHERE user_id=:user_id AND id=:id",
            {"user_id": ctx.author.id, "id": _id},
        )

        await ctx.reply(f"*Successfully deleted reminder #{_id}.*")

    @commands.command()
    async def remindme(
        self,
        ctx: Blimp.Context,
        when: Union[ParseableDatetime, ParseableTimedelta],
        *,
        text: str,
    ):
        """Add a timed reminder for yourself.

        <when> may be a timestamp in ISO 8601 format ("YYYY-MM-DD HH:MM:SS") or
        a delta from now, like "90 days" or 1h or "1 minute 30secs".

        You will be reminded either in this channel or via DM if the channel is
        no longer reachable."""
        due = None
        if isinstance(when, datetime):
            due = when
        elif isinstance(when, timedelta):
            due = ctx.message.created_at + when

        if due < datetime.utcnow():
            await ctx.reply(
                "*tempting as it seems*\n"
                "*it's best not to venture there*\n"
                "*let the past lie dead.*",
                subtitle="You can't set reminders for past events.",
                color=ctx.color.I_GUESS,
            )

        invoked = await ctx.reply(f"*Reminder set for {due}.*")

        ctx.database.execute(
            """INSERT INTO reminders_entries(user_id, message_oid, due, text)
            VALUES(:user_id, :message_oid, :due, :text);""",
            {
                "user_id": ctx.author.id,
                "message_oid": ctx.objects.make_object(
                    m=[invoked.channel.id, invoked.id]
                ),
                "due": due.isoformat(),
                "text": text,
            },
        )
