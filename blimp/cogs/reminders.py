import re
from datetime import datetime, timedelta, timezone
from typing import Optional, Union

import discord
from discord.ext import commands, tasks

from ..customizations import (
    Blimp,
    ParseableDatetime,
    ParseableTimedelta,
    UnableToComply,
)


class Reminders(Blimp.Cog):
    "Reminding you of things that you believe are going to happen."

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
            user = self.bot.get_user(entry["user_id"])

            try:
                channel = self.bot.get_channel(invoke_msg[0])
                member = channel.guild.get_member(entry["user_id"])

                # if the user can't read this channel or it doesn't exist anymore, try DMs
                if (
                    not channel
                    or not member
                    or not channel.permissions_for(member).read_messages
                ):
                    channel = user

                title = str(entry["text"])
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
            except Exception as exc:  # pylint: disable=broad-except
                self.log.error(
                    f"Failed to deliver reminder {entry['id']}, "
                    f"origin {await self.bot.represent_object({'m':invoke_msg})}",
                    exc_info=exc,
                )
            finally:
                self.bot.database.execute(
                    "DELETE FROM reminders_entries WHERE id=:id",
                    {"id": entry["id"]},
                )

    @commands.group(invoke_without_command=True, case_insensitive=True)
    async def reminders(self, ctx: Blimp.Context):
        """Reminders allow you to set notifications for a future self. When the time comes, BLIMP
        will ping you with a text you set and a link to the original message.

        **You can create reminders using `remindme$sfx`**"""

        await ctx.invoke_command("reminders list")

    @commands.command(parent=reminders, name="list")
    async def _list(self, ctx: Blimp.Context):
        "List all pending reminders for you in DMs."

        rems = ctx.database.execute(
            "SELECT * FROM reminders_entries WHERE user_id=:user_id",
            {"user_id": ctx.author.id},
        ).fetchall()

        if not rems:
            await ctx.reply("You have no pending reminders.", color=ctx.Color.I_GUESS)
            return

        rows = []
        for rem in rems:
            invoke_msg = ctx.objects.by_oid(rem["message_oid"])
            invoke_link = await self.bot.represent_object(invoke_msg)
            timestamp = datetime.fromisoformat(rem["due"]).replace(tzinfo=None)
            delta = timestamp - ctx.message.created_at
            delta = delta - timedelta(microseconds=delta.microseconds)
            rows.append(f"#{rem['id']} **{delta} ({invoke_link})**\n{rem['text']}")

        await Blimp.Context.reply(ctx.author, "\n".join(rows))

    @commands.command(parent=reminders)
    async def delete(self, ctx: Blimp.Context, number: int):
        """Delete one of your reminders.

        `number` is the number listed first in a `reminders$sfx list` row."""

        old = ctx.database.execute(
            "SELECT * FROM reminders_entries WHERE user_id=:user_id AND id=:id",
            {"user_id": ctx.author.id, "id": number},
        ).fetchone()
        if not old:
            raise UnableToComply(
                f"Can't delete your reminder #{number} as it doesn't exist."
            )

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

        `when` can be either a [duration]($manual#durations) from now or a [time
        stamp]($manual#timestamps). Either way, it determines when the reminder will fire.

        `text` is your reminder text. You can leave this empty.

        You will be reminded either in the channel where the command was issued or via DM if that
        channel is no longer reachable."""

        due = None
        if isinstance(when, datetime):
            due = when.replace(microsecond=0)
        elif isinstance(when, timedelta):
            if when == timedelta():
                raise commands.BadArgument("Time difference may not be zero.")

            due = (
                ctx.message.created_at.replace(microsecond=0, tzinfo=timezone.utc)
                + when
            )

        if not text:
            text = "[no reminder text provided]"

        if due < datetime.now(timezone.utc):
            raise UnableToComply("You can't set reminders for past events.")

        cursor = ctx.database.execute(
            """INSERT INTO reminders_entries(user_id, message_oid, due, text)
            VALUES(:user_id, :message_oid, :due, :text);""",
            {
                "user_id": ctx.author.id,
                "message_oid": ctx.objects.make_object(
                    m=[ctx.channel.id, ctx.message.id]
                ),
                "due": due.astimezone(tz=timezone.utc).isoformat(sep=" "),
                "text": text,
            },
        )

        await ctx.reply(
            f"*Reminder #{cursor.lastrowid} set for {due.replace(tzinfo=None)} UTC.*"
        )
