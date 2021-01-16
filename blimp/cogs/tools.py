import asyncio
import pprint
import tempfile
import traceback
from datetime import timedelta
from typing import Optional, Union

import discord
import toml
from discord.ext import commands

from ..customizations import Blimp, ParseableTimedelta, UnableToComply, Unauthorized
from ..message_formatter import create_message_dict
from ..transcript import Transcript
from .alias import (
    MaybeAliasedCategoryChannel,
    MaybeAliasedMessage,
    MaybeAliasedTextChannel,
)


class Tools(Blimp.Cog):
    "Semi-useful things, actually."

    last_eval_result = None

    @commands.command()
    async def cleanup(self, ctx: Blimp.Context, limit: int = 20, any_bot: bool = False):
        """Go through the last messages and delete bot responses.

        `limit` controls the amount of messages searched, the default is 20.

        `any_bot` determines if only BLIMP's (the default) or all bots' messages are cleared."""

        if not ctx.privileged_modify(ctx.channel):
            raise Unauthorized()

        async with ctx.typing():
            purged = await ctx.channel.purge(
                limit=limit,
                check=lambda msg: msg.author == ctx.bot.user
                or (any_bot and msg.author.bot),
            )

        info = await ctx.reply(
            f"*Deleted {len(purged)} of {limit} messages. "
            "This message will self-destruct in five seconds.*"
        )
        await asyncio.sleep(5.0)
        await info.delete()

    @commands.command()
    async def stalechannels(
        self,
        ctx: Blimp.Context,
        category: MaybeAliasedCategoryChannel,
        duration: ParseableTimedelta = ParseableTimedelta(days=2),
    ):
        """List channels haven't been for a certain duration.

        `category` is the channel category that should be inspected.

        `duration` is a [duration]($manual#durations). Channels that haven't received any messages
        during this time are considered stale and will be printed. Defaults to two days."""

        channels = []
        for channel in category.channels:
            if (
                not isinstance(channel, discord.TextChannel)
                or not channel.last_message_id
            ):
                continue

            timestamp = discord.utils.snowflake_time(channel.last_message_id)
            delta = ctx.message.created_at - timestamp

            # chop off ms
            delta = delta - ParseableTimedelta(microseconds=delta.microseconds)
            if delta > duration:
                channels.append((channel, delta))

        await ctx.reply(
            "\n".join(
                [f"{channel.mention} {delta} ago" for channel, delta in channels]
            ),
            subtitle=f"Channels in {category.name} that haven't been used in {duration}",
        )

    @commands.command()
    async def eval(self, ctx: Blimp.Context, *, code: str):
        "Parse a code block as a function body and execute it. No, you can't use this."

        if not await ctx.bot.is_owner(ctx.author):
            raise Unauthorized()

        code = code.removeprefix("```py").strip("\n` ")
        lines = code.splitlines()

        # if the code is just a single expression, turn it into a return statement
        if len(lines) == 1:
            try:
                # this will fail if it's already a statement
                compile(lines[0], "", "eval")
                lines[0] = f"return {lines[0]}"
            except SyntaxError:
                pass

        lines.insert(0, "global plain")
        code = "async def apply():\n" + "\n".join([f"    {line}" for line in lines])

        printer = pprint.PrettyPrinter(width=56)
        try:
            environment = {
                "ctx": ctx,
                "_": self.last_eval_result,
                "plain": False,
            }
            compiled = compile(
                code,
                "The Empty String",
                "exec",
                optimize=0,
            )
            exec(compiled, environment)  # pylint: disable=exec-used
            self.last_eval_result = await environment["apply"]()

            if self.last_eval_result is None:
                await ctx.message.add_reaction("✅")
                return

            if environment["plain"]:
                await ctx.reply(self.last_eval_result)
            else:
                pretty = printer.pformat(self.last_eval_result)
                await ctx.reply(f"```py\n{pretty}```")

        except Exception as ex:  # pylint: disable=broad-except
            entries = traceback.extract_tb(ex.__traceback__)
            for entry in entries:
                if entry.filename == "The Empty String":
                    entry._line = code.splitlines()[  # pylint: disable=protected-access
                        entry.lineno - 1
                    ]

            tb_lines = "".join(traceback.format_list(entries))
            await ctx.reply(f"```py\n{ex}\n{tb_lines}```", color=ctx.Color.BAD)

    @commands.command()
    async def pleasetellmehowmanypeoplehave(
        self, ctx: Blimp.Context, role: discord.Role
    ):
        """Show how many members have a certain role.

        `role` is the role whose members should be counted."""

        members = [m for m in ctx.guild.members if role in m.roles]
        await ctx.reply(f"{len(members)} members have {role.mention}.")

    @commands.command()
    async def setchanneltopic(
        self,
        ctx: Blimp.Context,
        channel: Optional[MaybeAliasedTextChannel],
        *,
        text: str,
    ):
        """Set the description of a channel.

        `channel` is the channel to edit. If left empty, BLIMP works with the current channel.

        `text` is the new description of the channel. Standard Discord formatting works."""

        if not channel:
            channel = ctx.channel

        if not ctx.privileged_modify(channel):
            raise Unauthorized()

        if len(text) > 1024:
            raise UnableToComply(f"Proposed topic is too long ({len(text)}/1024)")

        log_embed = (
            discord.Embed(
                description=f"{ctx.author} updated the topic of {channel.mention}.",
                color=ctx.Color.I_GUESS,
            )
            .add_field(name="Old", value=channel.topic)
            .add_field(name="New", value=text)
        )

        await channel.edit(topic=text, reason=str(ctx.author))

        await ctx.bot.post_log(channel.guild, embed=log_embed)
        await ctx.reply(f"Updated channel topic for {channel.mention}.")

    @commands.command()
    async def setchannelname(
        self,
        ctx: Blimp.Context,
        channel: Optional[MaybeAliasedTextChannel],
        *,
        text: str,
    ):
        """Set the name of a channel.

        `channel` is the channel to edit. If left empty, BLIMP works with the current channel.

        `text` is the new name of the channel."""

        if not channel:
            channel = ctx.channel

        if not ctx.privileged_modify(channel):
            raise Unauthorized()

        if len(text) > 100:
            raise UnableToComply(f"Proposed name is too long ({len(text)}/1024)")

        log_embed = (
            discord.Embed(
                description=f"{ctx.author} updated the name of {channel.mention}.",
                color=ctx.Color.I_GUESS,
            )
            .add_field(name="Old", value=channel.name)
            .add_field(name="New", value=text)
        )

        await channel.edit(name=text, reason=str(ctx.author))

        await ctx.bot.post_log(channel.guild, embed=log_embed)
        await ctx.reply(f"Updated channel name for {channel.mention}.")

    @commands.command()
    async def post(
        self,
        ctx: Blimp.Context,
        where: Union[MaybeAliasedTextChannel, MaybeAliasedMessage],
        *,
        text: str,
    ):
        """Make BLIMP post something on your behalf.

        `where` is either a channel to post in, or a previous `post$sfx`-created message to edit.

        `text` is the new content of the message. [Advanced Message
        Formatting]($manual#advanced-message-formatting) is available."""

        if not ctx.privileged_modify(where.guild):
            raise Unauthorized()

        try:
            text = toml.dumps(toml.loads(text))
        except toml.TomlDecodeError:
            pass

        if isinstance(where, discord.TextChannel):
            message = await where.send(**create_message_dict(text, where))
            ctx.database.execute(
                "INSERT INTO post_entries(message_oid, text) VALUES(:oid, :text)",
                {
                    "oid": ctx.objects.make_object(m=[message.channel.id, message.id]),
                    "text": text,
                },
            )
            await ctx.bot.post_log(
                where.guild,
                embed=discord.Embed(
                    description=f"{ctx.author} created a "
                    f"[BLIMP post in #{message.channel.name}]({message.jump_url}).",
                    color=ctx.Color.I_GUESS,
                ).add_field(name="New", value=text),
            )
        else:
            old = ctx.database.execute(
                "SELECT * FROM post_entries WHERE message_oid=:oid",
                {"oid": ctx.objects.by_data(m=[where.channel.id, where.id])},
            ).fetchone()
            if not old:
                return

            ctx.database.execute(
                "UPDATE post_entries SET text=:text WHERE message_oid=:oid",
                {
                    "text": text,
                    "oid": ctx.objects.by_data(m=[where.channel.id, where.id]),
                },
            )
            await where.edit(**create_message_dict(text, where.channel))
            await ctx.bot.post_log(
                where.guild,
                embed=discord.Embed(
                    description=f"{ctx.author} updated a "
                    f"[BLIMP post in #{where.channel.name}]({where.jump_url}).",
                    color=ctx.Color.I_GUESS,
                )
                .add_field(name="Old", value=old["text"])
                .add_field(name="New", value=text),
            )

    @commands.command()
    async def transcript(
        self,
        ctx: Blimp.Context,
        channel: Optional[MaybeAliasedTextChannel],
        start_with: Optional[MaybeAliasedMessage],
        end_with: Optional[MaybeAliasedMessage],
    ):
        """Create a transcript of a channel.

        `channel` is the channel to transcribe. If left empty, BLIMP will work with the current
        channel.

        `start_with` is the first message that should appear in the transcript.

        `end_with` is the last message that should appear in the transcript.

        There is a hard limit of 2000 messages getting transcribed at once."""

        if not channel:
            channel = ctx.channel

        if not ctx.privileged_modify(channel):
            raise Unauthorized()

        with tempfile.TemporaryFile(mode="r+") as temp:
            messages = await Transcript.write_transcript(
                temp,
                channel,
                first_message_id=None if not start_with else start_with.id,
                last_message_id=None if not end_with else end_with.id,
            )
            temp.seek(0)

            first_ts = discord.utils.snowflake_time(messages[0].id)
            first_ts = first_ts - timedelta(microseconds=first_ts.microsecond)

            last_ts = discord.utils.snowflake_time(messages[-1].id)
            last_ts = last_ts - timedelta(microseconds=last_ts.microsecond)

            archive_embed = discord.Embed(
                title=f"#{channel.name}",
                color=ctx.Color.I_GUESS,
            ).add_field(
                name="Transcript",
                value=f"From {first_ts}\nTo {last_ts}\n{len(messages)} messages",
            )

            participants = {message.author for message in messages}
            archive_embed.add_field(
                name="Participants",
                value="\n".join(user.mention for user in participants),
            )

            await ctx.channel.send(
                embed=archive_embed,
                file=discord.File(fp=temp, filename=f"{channel.name}.html"),
            )
