from datetime import datetime, timezone

import discord
from discord.ext import commands

from ..customizations import Blimp, UnableToComply, Unauthorized
from .alias import MaybeAliasedMessage


class Triggers(Blimp.Cog):
    "The Big Red Button."

    @commands.group()
    async def trigger(self, ctx: Blimp.Context):
        """Triggers allow your users to invoke pre-set commands by reacting to a specific message.
        BLIMP uses this to allow easy ticket deletion. The possibilities, however, are limitless.
        Commands are always ran as the user that reacts to the post."""

    @commands.command(parent=trigger)
    async def update(
        self, ctx: Blimp.Context, msg: MaybeAliasedMessage, emoji: str, *, command: str
    ):
        """
        Update a trigger, overwriting its setup entirely.

        `msg` is the message a trigger should be created/edited on.

        `emoji` is the reaction the trigger should be sensitive to.

        `command` is the command to execute when the reaction is used."""

        if not ctx.privileged_modify(msg.guild):
            raise Unauthorized()

        log_embed = discord.Embed(
            description=f"{ctx.author} updated "
            f"[trigger {emoji} in #{msg.channel.name}]({msg.jump_url}).",
            color=ctx.Color.I_GUESS,
        )

        old = ctx.database.execute(
            "SELECT * FROM trigger_entries WHERE message_oid=:message_oid AND emoji=:emoji",
            {
                "message_oid": ctx.objects.by_data(m=[msg.channel.id, msg.id]),
                "emoji": emoji,
            },
        ).fetchone()
        if old:
            log_embed.add_field(
                name="Old", value=old["command"],
            )

        log_embed.add_field(
            name="New", value=command,
        )

        await msg.add_reaction(emoji)

        ctx.database.execute(
            """INSERT OR REPLACE INTO
            trigger_entries(message_oid, emoji, command)
            VALUES(:message_oid, :emoji, :command)""",
            {
                "message_oid": ctx.objects.make_object(m=[msg.channel.id, msg.id]),
                "emoji": emoji,
                "command": command,
            },
        )

        await ctx.bot.post_log(msg.guild, embed=log_embed)

        await ctx.reply(
            f"*Overwrote [trigger {emoji} in #{msg.channel.name}]({msg.jump_url}).*"
        )

    @commands.command(parent=trigger)
    async def delete(self, ctx: Blimp.Context, msg: MaybeAliasedMessage, emoji: str):
        """Delete a trigger, but not the message.

        `msg` is the message to delete a trigger on.

        `emoji` is the reaction BLIMP should no longer consider a trigger."""

        if not ctx.privileged_modify(msg.guild):
            raise Unauthorized()

        cursor = ctx.database.execute(
            "DELETE FROM trigger_entries WHERE message_oid=:message_oid AND emoji=:emoji",
            {
                "message_oid": ctx.objects.by_data(m=[msg.channel.id, msg.id]),
                "emoji": emoji,
            },
        )
        if cursor.rowcount == 0:
            raise UnableToComply(
                f"Can't delete trigger [trigger {emoji} in #{msg.channel.name}]({msg.jump_url}) "
                "as it doesn't exist."
            )

        await msg.remove_reaction(emoji, ctx.guild.me)

        await ctx.reply(
            f"*Deleted [trigger {emoji} in #{msg.channel.name}]({msg.jump_url}).*"
        )

    @Blimp.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        "On reaction creation, check if we should add roles and do so."
        if not payload.guild_id or payload.user_id == self.bot.user.id:
            return

        channel = self.bot.get_channel(payload.channel_id)
        trigger = self.bot.database.execute(
            "SELECT * FROM trigger_entries WHERE message_oid=:message_oid AND emoji=:emoji",
            {
                "message_oid": self.bot.objects.by_data(
                    m=[payload.channel_id, payload.message_id]
                ),
                "emoji": str(payload.emoji),
            },
        ).fetchone()
        if not trigger:
            return

        # Had I been able to feel anything after writing this, it would've been disgust.
        message = await channel.fetch_message(payload.message_id)
        actual_id = message.id

        message.author = channel.guild.get_member(payload.user_id)
        message.content = trigger["command"]
        message.id = discord.utils.time_snowflake(
            datetime.now(tz=timezone.utc).replace(tzinfo=None)
        )
        await self.bot.process_commands(message)

        message.id = actual_id
        try:
            await message.remove_reaction(
                payload.emoji, channel.guild.get_member(payload.user_id)
            )
        except discord.errors.NotFound:
            pass
