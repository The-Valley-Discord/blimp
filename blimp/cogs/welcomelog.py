import json
from string import Template

import discord
import toml
from discord.ext import commands

from ..customizations import Blimp, UnableToComply, Unauthorized
from ..message_formatter import create_message_dict
from .alias import MaybeAliasedTextChannel


class WelcomeLog(Blimp.Cog):
    "Greeting and goodbye-ing people."

    @staticmethod
    def member_variables(member: discord.Member) -> dict:
        "Extract the greeting template variables from a member object."
        return {
            "user": member.mention,
            "id": member.id,
            "tag": str(member),
            "avatar": member.avatar,
        }

    @commands.group(invoke_without_command=True, case_insensitive=True)
    async def welcome(self, ctx: Blimp.Context):
        """Welcome allows you to greet users that join your server. The automated greeting is highly
        flexible, but probably unsuitable for security purposes. For that you probably want a
        dedicated logging bot!

        Inside greeting texts, the following **variables** are available: `$user` mentions the
        member, `$id` is their ID, `$tag` is their DiscordTag#1234, and `$avatar` is their avatar.
        [Advanced Message Formatting]($manual#advanced-message-formatting) is available in
        greetings.
        """

        await ctx.invoke_command("welcome view")

    @commands.command(parent=welcome, name="update")
    async def w_update(
        self, ctx: Blimp.Context, channel: MaybeAliasedTextChannel, *, greeting: str
    ):
        """Update user-facing join messages for this server.

        `channel` is the channel where join greetings will be posted.

        `greeting` is the text of the greeting messages. [Advanced Message
        Formatting]($manual#advanced-message-formatting) is available."""

        if not ctx.privileged_modify(channel.guild):
            raise Unauthorized()

        logging_embed = discord.Embed(
            description=f"{ctx.author} updated Welcome.", color=ctx.Color.I_GUESS
        )

        try:
            greeting = toml.dumps(toml.loads(greeting))
        except toml.TomlDecodeError:
            pass

        old = ctx.database.execute(
            "SELECT * FROM welcome_configuration WHERE oid=:oid",
            {"oid": ctx.objects.by_data(g=channel.guild.id)},
        ).fetchone()
        if old and old["join_data"]:
            data = json.loads(old["join_data"])
            old_channel = ctx.objects.by_oid(data[0])["tc"]
            logging_embed.add_field(
                name="Old", value=f"<#{old_channel}>```toml\n{data[1]}```"
            )

        ctx.database.execute(
            """INSERT INTO welcome_configuration(oid, join_data) VALUES(:oid, json(:data))
            ON CONFLICT(oid) DO UPDATE SET join_data=excluded.join_data""",
            {
                "oid": ctx.objects.make_object(g=channel.guild.id),
                "data": json.dumps([ctx.objects.make_object(tc=channel.id), greeting]),
            },
        )

        logging_embed.add_field(
            name="New", value=f"<#{channel.id}>```toml\n{greeting}```"
        )
        await self.bot.post_log(ctx.guild, embed=logging_embed)

        await ctx.reply("Overwrote Welcome configuration, example message follows:")
        await ctx.send(
            **create_message_dict(
                Template(greeting).safe_substitute(
                    self.member_variables(channel.guild.me)
                ),
                ctx.channel,
            )
        )

    @commands.command(parent=welcome, name="view")
    async def w_view(self, ctx: Blimp.Context):
        "View the current configuration for user-facing join messages."

        if not ctx.privileged_modify(ctx.guild):
            raise Unauthorized()

        old = ctx.database.execute(
            "SELECT * FROM welcome_configuration WHERE oid=:oid",
            {"oid": ctx.objects.by_data(g=ctx.guild.id)},
        ).fetchone()
        if not old or not old["join_data"]:
            raise UnableToComply("Welcome isn't configured for this guild.")

        data = json.loads(old["join_data"])
        old_channel = ctx.objects.by_oid(data[0])["tc"]
        await ctx.reply(
            f"Welcome messages are posted into <#{old_channel}>, using this configuration:```toml\n"
            + data[1]
            + "```\nExample message follows:"
        )
        await ctx.send(
            **create_message_dict(
                Template(data[1]).safe_substitute(self.member_variables(ctx.guild.me)),
                ctx.channel,
            )
        )

    @commands.command(parent=welcome, name="disable")
    async def w_disable(self, ctx: Blimp.Context):
        "Disable the server's welcome greetings and delete the configuration."

        if not ctx.privileged_modify(ctx.guild):
            raise Unauthorized()

        cursor = ctx.database.execute(
            "UPDATE welcome_configuration SET join_data=NULL WHERE oid=:oid",
            {"oid": ctx.objects.make_object(g=ctx.guild.id)},
        )
        if cursor.rowcount == 0:
            raise UnableToComply(
                "Can't delete Welcome configuration as it doesn't exist."
            )

        await self.bot.post_log(ctx.guild, f"{ctx.author} disabled Welcome.")

        await ctx.reply("Deleted welcome configuration.")

    @Blimp.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        "Look up if we have a configuration for this guild and greet if so."

        objects = self.bot.objects

        cursor = self.bot.database.execute(
            "SELECT * FROM welcome_configuration WHERE oid=:oid",
            {"oid": objects.by_data(g=member.guild.id)},
        )
        row = cursor.fetchone()
        if not row or not row["join_data"]:
            return

        data = json.loads(row["join_data"])
        channel = self.bot.get_channel(objects.by_oid(data[0])["tc"])

        await channel.send(
            **create_message_dict(
                Template(data[1]).safe_substitute(self.member_variables(member)),
                channel,
            )
        )

    @commands.group(invoke_without_command=True, case_insensitive=True)
    async def goodbye(self, ctx: Blimp.Context):
        """Goodbye allows you to see off users that leave your server. The automated goodbye is
        highly flexible, but probably unsuitable for security purposes. For that you probably want a
        dedicated logging bot!

        Inside goodbye messages, the following **variables** are available: `$user` mentions the
        member, `$id` is their ID, `$tag` is their DiscordTag#1234, and `$avatar` is their avatar.
        [Advanced Message Formatting]($manual#advanced-message-formatting) is available in
        goodbye messages.
        """

        await ctx.invoke_command("goodbye view")

    @commands.command(parent=goodbye, name="update")
    async def g_update(
        self, ctx: Blimp.Context, channel: MaybeAliasedTextChannel, *, greeting: str
    ):
        """Update user-facing leave messages for this server.

        `channel` is the channel where goodbye messages will be posted.

        `greeting` is the text of the goodbye messages. [Advanced Message
        Formatting]($manual#advanced-message-formatting) is available."""

        if not ctx.privileged_modify(channel.guild):
            raise Unauthorized()

        logging_embed = discord.Embed(
            description=f"{ctx.author} updated Goodbye.", color=ctx.Color.I_GUESS
        )

        try:
            greeting = toml.dumps(toml.loads(greeting))
        except toml.TomlDecodeError:
            pass

        old = ctx.database.execute(
            "SELECT * FROM welcome_configuration WHERE oid=:oid",
            {"oid": ctx.objects.by_data(g=channel.guild.id)},
        ).fetchone()
        if old and old["leave_data"]:
            data = json.loads(old["leave_data"])
            old_channel = ctx.objects.by_oid(data[0])["tc"]
            logging_embed.add_field(
                name="Old", value=f"<#{old_channel}>```toml\n{data[1]}```"
            )

        ctx.database.execute(
            """INSERT INTO welcome_configuration(oid, leave_data) VALUES(:oid, json(:data))
            ON CONFLICT(oid) DO UPDATE SET leave_data=excluded.leave_data""",
            {
                "oid": ctx.objects.make_object(g=channel.guild.id),
                "data": json.dumps([ctx.objects.make_object(tc=channel.id), greeting]),
            },
        )

        logging_embed.add_field(
            name="New", value=f"<#{channel.id}>```toml\n{greeting}```"
        )
        await self.bot.post_log(ctx.guild, embed=logging_embed)

        await ctx.reply("Overwrote Goodbye configuration, example message follows:")
        await ctx.send(
            **create_message_dict(
                Template(greeting).safe_substitute(
                    self.member_variables(channel.guild.me)
                ),
                channel,
            )
        )

    @commands.command(parent=goodbye, name="view")
    async def g_view(self, ctx: Blimp.Context):
        "View the current configuration for user-facing leave messages."

        if not ctx.privileged_modify(ctx.guild):
            raise Unauthorized()

        old = ctx.database.execute(
            "SELECT * FROM welcome_configuration WHERE oid=:oid",
            {"oid": ctx.objects.by_data(g=ctx.guild.id)},
        ).fetchone()
        if not old or not old["leave_data"]:
            raise UnableToComply("Goodbye isn't configured for this guild.")

        data = json.loads(old["leave_data"])
        old_channel = ctx.objects.by_oid(data[0])["tc"]
        await ctx.reply(
            f"Goodbye messages are posted into <#{old_channel}>, using this configuration:```toml\n"
            + data[1]
            + "```\nExample message follows:"
        )
        await ctx.send(
            **create_message_dict(
                Template(data[1]).safe_substitute(self.member_variables(ctx.guild.me)),
                ctx.channel,
            )
        )

    @commands.command(parent=goodbye, name="disable")
    async def g_disable(self, ctx: Blimp.Context):
        "Disable the server's goodbye messages and delete the configuration."

        if not ctx.privileged_modify(ctx.guild):
            raise Unauthorized()

        cursor = ctx.database.execute(
            "UPDATE welcome_configuration SET leave_data=NULL WHERE oid=:oid",
            {"oid": ctx.objects.make_object(g=ctx.guild.id)},
        )
        if cursor.rowcount == 0:
            raise UnableToComply(
                "Can't delete Goodbye configuration as it doesn't exist."
            )

        await self.bot.post_log(ctx.guild, f"{ctx.author} disabled Goodbye.")

        await ctx.reply("Deleted Goodbye configuration.")

    @Blimp.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        "Look up if we have a configuration for this guild and say goodbye if so."
        objects = self.bot.objects

        cursor = self.bot.database.execute(
            "SELECT * FROM welcome_configuration WHERE oid=:oid",
            {"oid": objects.by_data(g=member.guild.id)},
        )
        row = cursor.fetchone()
        if not row or not row["leave_data"]:
            return

        data = json.loads(row["leave_data"])
        channel = self.bot.get_channel(objects.by_oid(data[0])["tc"])

        await channel.send(
            **create_message_dict(
                Template(data[1]).safe_substitute(self.member_variables(member)),
                channel,
            )
        )
