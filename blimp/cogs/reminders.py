from datetime import datetime, timedelta, timezone
import re
from typing import Union, Optional

import discord
from discord.ext import commands, tasks

from customizations import Blimp, ParseableDatetime, ParseableTimedelta


class Reminders(Blimp.Cog):
    """*Reminding you of things that you believe are going to happen.*
    Reminders allow you to set notifications for a future self. When the time
    comes, BLIMP will ping you with a text you set and a link to the original
    message."""

    def __init__(self, *args):
        self.execute_reminders.start()  # pylint: disable=no-member
        super().__init__(*args)

    @tasks.loop(seconds=0.5)
    async def execute_reminders(self):
        "Look at overdue reminders and send notifications out."
        cursor = self.bot.database.execute(
            "SELECT * FROM reminders_entries WHERE due < datetime('now')"
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
                self.log.warn(
                    f"Failed to deliver reminder {entry['id']}, origin {self.bot.represent_object(invoke_msg)}"
                )
                pass
            finally:
                self.bot.database.execute(
                    "DELETE FROM reminders_entries WHERE id=:id", {"id": entry["id"]},
                )

            title = entry["text"]
            extratext = ""
            if len(title) > 255:
                extratext = "…" + title[255:]
                title = title[:255] + "…"

            # mentions/links don't work in the embed title
            if re.search(r"<(?:@!?|#|@&)\d{10,}>", entry["text"]) or re.search(
                "https://discord(?:app)?.com/channels/", entry["text"]
            ):
                title = None
                extratext = entry["text"]

            timestamp = (
                discord.utils.snowflake_time(invoke_msg[1])
                .replace(microsecond=0, tzinfo=timezone.utc)
                .replace(tzinfo=None)
            )
            await channel.send(
                self.bot.get_user(entry["user_id"]).mention,
                embed=discord.Embed(
                    title=title,
                    description=extratext
                    + f"\n\n**Context:** {await self.bot.represent_object({'m':invoke_msg})}",
                ).set_footer(text=f"Reminder from {timestamp} UTC"),
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
            timestamp = datetime.fromisoformat(rem["due"]).replace(tzinfo=None)
            delta = timestamp - ctx.message.created_at
            delta = delta - timedelta(microseconds=delta.microseconds)
            rows.append(f"#{rem['id']} **{delta} ({invoke_link})**\n{rem['text']}")

        await ctx.reply("\n".join(rows))

    @commands.command(parent=reminders)
    async def delete(self, ctx: Blimp.Context, number: int):
        "Delete one of your reminders."

        old = ctx.database.execute(
            "SELECT * FROM reminders_entries WHERE user_id=:user_id AND id=:id",
            {"user_id": ctx.author.id, "id": number},
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
            {"user_id": ctx.author.id, "id": number},
        )

        await ctx.reply(f"*Successfully deleted reminder #{number}.*")

    @commands.command()
    async def remindme(
        self,
        ctx: Blimp.Context,
        when: Union[ParseableDatetime, ParseableTimedelta],
        *,
        text: Optional[str],
    ):
        """Add a timed reminder for yourself.

        `when` may be a timestamp in ISO 8601 format ("YYYY-MM-DD HH:MM:SS") or
        a delta from now, like "90 days" or 1h or "1 minute 30secs".
        You will be reminded either in this channel or via DM if the channel is
        no longer reachable."""
        due = None
        if isinstance(when, datetime):
            due = when.replace(microsecond=0)
        elif isinstance(when, timedelta):
            due = (
                ctx.message.created_at.replace(microsecond=0, tzinfo=timezone.utc)
                + when
            )

        if not text:
            text = "[no reminder text provided]"

        if due < datetime.now(timezone.utc):
            await ctx.reply(
                "*tempting as it seems*\n"
                "*it's best not to venture there*\n"
                "*let the past lie dead.*",
                subtitle="You can't set reminders for past events.",
                color=ctx.Color.I_GUESS,
            )
            return

        invoked = await ctx.reply(f"*Reminder set for {due.replace(tzinfo=None)} UTC.*")

        ctx.database.execute(
            """INSERT INTO reminders_entries(user_id, message_oid, due, text)
            VALUES(:user_id, :message_oid, :due, :text);""",
            {
                "user_id": ctx.author.id,
                "message_oid": ctx.objects.make_object(
                    m=[invoked.channel.id, invoked.id]
                ),
                "due": due.astimezone(tz=timezone.utc).isoformat(sep=" "),
                "text": text,
            },
        )
