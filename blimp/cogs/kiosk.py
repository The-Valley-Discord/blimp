import json
import re
from typing import List, Tuple, Union

import discord
from discord.ext import commands

from ..customizations import Blimp, PleaseRestate, UnableToComply, Unauthorized
from .alias import MaybeAliasedMessage


class Kiosk(Blimp.Cog):
    "Handing out fancy badges."

    @commands.group()
    async def kiosk(self, ctx: Blimp.Context):
        """Kiosks allow users to pick roles by reacting to specific messages with certain reactions.
        This is frequently used for pronouns, ping roles, opt-ins or colors. Every Kiosk has its own
        set of reaction-role pairings."""

    @staticmethod
    def parse_emoji_pairs(args: List[Union[discord.Role, str]]):
        "Get the internal representation of an argument list."

        result = []
        # iterate over pairs of args
        pairwise = iter(args)
        for (emoji, role) in zip(pairwise, pairwise):
            emoji_id = re.search(r"(\d{10,})>?$", emoji)
            if emoji_id:
                emoji = int(emoji_id[1])

            result.append((emoji, role))

        return result

    def render_emoji_pairs(
        self,
        pairs: List[Tuple[Union[int, str], Union[int, discord.Role]]],
        separator: str,
    ) -> str:
        """Turn the stored data into a human-readable representation.

        Expects any combination of [("unicode_emoji", <Role Object>), (custom emoji id, role id)]"""

        result = []
        for maybe_emoji, maybe_role in pairs:
            emoji = maybe_emoji
            if isinstance(emoji, int):
                emoji = self.bot.get_emoji(maybe_emoji) or (
                    "<:emoji:" + str(maybe_emoji) + ">"
                )
            role_id = getattr(maybe_role, "id", maybe_role)

            result.append(f"{emoji} <@&{role_id}>")

        return separator.join(result)

    @commands.command(parent=kiosk)
    async def update(
        self,
        ctx: Blimp.Context,
        msg: MaybeAliasedMessage,
        args: commands.Greedy[Union[discord.Role, str]],
    ):
        """
        Update (or create) a role kiosk, overwriting its setup entirely.

        `args` is a space-separated list of one emoji each followed by one role. This determines the
        options the kiosk will have available. Due to Discord limitations, only 20 pairs are
        possible per message.
        """

        if not ctx.privileged_modify(msg.guild):
            return

        result = self.parse_emoji_pairs(args)

        if len(result) == 0:
            await ctx.reply(
                "**Please restate query:** No valid reaction-role pairings found.",
                color=ctx.Color.BAD,
            )
            return

        if len(result) > 20:
            raise UnableToComply(
                "You can't use more than 20 reaction-role pairs per message.",
            )

        user_failed_roles = []
        bot_failed_roles = []
        for _, role in result:
            if not ctx.privileged_modify(role):
                user_failed_roles.append(role)
            if not ctx.me.top_role > role:
                bot_failed_roles.append(role)

        if user_failed_roles:
            raise Unauthorized(
                "You can't modify the following roles: "
                + " ".join([r.mention for r in user_failed_roles])
                + "\nYour highest role needs to be above all of them.",
            )

        if bot_failed_roles:
            raise UnableToComply(
                "BLIMP can't modify the following roles: "
                + " ".join([r.mention for r in bot_failed_roles])
                + "\nThe bot's highest role needs to be above all of them.",
            )

        result = [(emoji, role.id) for (emoji, role) in result]

        for emoji in [item for item in msg.reactions if item.me]:
            await msg.remove_reaction(
                emoji.emoji, ctx.guild.get_member(ctx.bot.user.id)
            )

        for emoji in [item for item in args if item.__class__ == str]:
            await msg.add_reaction(emoji)

        log_embed = discord.Embed(
            description=f"{ctx.author} updated "
            f"[role kiosk in #{msg.channel.name}]({msg.jump_url}).",
            color=ctx.Color.I_GUESS,
        )

        old = ctx.database.execute(
            "SELECT * FROM rolekiosk_entries WHERE oid=:oid",
            {"oid": ctx.objects.by_data(m=[msg.channel.id, msg.id])},
        ).fetchone()
        if old:
            log_embed.add_field(
                name="Old",
                value=self.render_emoji_pairs(json.loads(old["data"]), "\n"),
            )

        log_embed.add_field(
            name="New",
            value=self.render_emoji_pairs(result, "\n"),
        )

        ctx.database.execute(
            "INSERT OR REPLACE INTO rolekiosk_entries(oid, data) VALUES(:oid,json(:data))",
            {
                "oid": ctx.objects.make_object(m=[msg.channel.id, msg.id]),
                "data": json.dumps(result),
            },
        )

        await ctx.bot.post_log(msg.guild, embed=log_embed)

        await ctx.reply(
            f"*Overwrote [role kiosk in #{msg.channel.name}]({msg.jump_url}).*"
        )

    @commands.command(parent=kiosk)
    async def append(
        self,
        ctx: Blimp.Context,
        msg: MaybeAliasedMessage,
        args: commands.Greedy[Union[discord.Role, str]],
    ):
        """
        Update a kiosk, appending options to it instead of overwriting.

        `args` is a space-separated list of one emoji each followed by one role. This determines the
        options the kiosk will have available. Due to Discord limitations, only 20 pairs are
        possible per message.
        """

        if not ctx.privileged_modify(msg.guild):
            return

        old = ctx.database.execute(
            "SELECT * FROM rolekiosk_entries WHERE oid=:oid",
            {"oid": ctx.objects.by_data(m=[msg.channel.id, msg.id])},
        ).fetchone()

        if not old:
            raise UnableToComply(
                "Message isn't a kiosk yet. Create one using `kiosk"
                + ctx.bot.config["discord"]["suffix"]
                + " update` first.",
            )

        pair_string = self.render_emoji_pairs(
            json.loads(old["data"]) + self.parse_emoji_pairs(args),
            " ",
        )

        text = f"kiosk{ctx.bot.suffix} update {msg.channel.id}-{msg.id} {pair_string}"

        await ctx.reply(
            text,
            subtitle="Automagically invoking this command…",
            color=ctx.Color.AUTOMATIC_BLUE,
        )

        async with ctx.typing():
            await ctx.invoke_command(text)

    @commands.command(parent=kiosk)
    async def view(self, ctx: Blimp.Context, msg: MaybeAliasedMessage):
        """View the current configuration of a Kiosk.

        `msg` is the message the Kiosk you're interested in is attached to."""

        row = ctx.database.execute(
            "SELECT * FROM rolekiosk_entries WHERE oid=:oid",
            {"oid": ctx.objects.by_data(m=[msg.channel.id, msg.id])},
        ).fetchone()
        if row:
            await ctx.reply(
                f"**[Role kiosk in #{msg.channel.name}]({msg.jump_url})**\n"
                + self.render_emoji_pairs(json.loads(row["data"]), "\n"),
            )
        else:
            raise UnableToComply("That message is not a Kiosk.")

    @commands.command(parent=kiosk)
    async def delete(
        self,
        ctx: Blimp.Context,
        msg: MaybeAliasedMessage,
    ):
        "Delete a role kiosk (but not the message)."

        if not ctx.privileged_modify(msg.guild):
            return

        cursor = ctx.database.execute(
            "DELETE FROM rolekiosk_entries WHERE oid=:oid",
            {"oid": ctx.objects.by_data(m=[msg.channel.id, msg.id])},
        )
        if cursor.rowcount == 0:
            raise PleaseRestate(
                "That message is not a Kiosk.",
            )

        for emoji in [item for item in msg.reactions if item.me]:
            await msg.remove_reaction(emoji.emoji, ctx.guild.me)

        await ctx.reply(
            f"*Deleted [role kiosk in #{msg.channel.name}]({msg.jump_url}).*"
        )

    def roles_from_payload(
        self, payload: discord.RawReactionActionEvent
    ) -> List[discord.Role]:
        "Turn a reaction payload into a list of roles to apply or take away."

        cursor = self.bot.database.execute(
            "SELECT data FROM rolekiosk_entries WHERE oid=:oid",
            {
                "oid": self.bot.objects.by_data(
                    m=[payload.channel_id, payload.message_id]
                )
            },
        )
        result = cursor.fetchone()
        if not result:
            return None

        data = json.loads(result["data"])
        return [
            self.bot.get_guild(payload.guild_id).get_role(number)
            for (emoji, number) in data
            if emoji in (payload.emoji.name, payload.emoji.id)
        ]

    @Blimp.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        "On reaction creation, check if we should add roles and do so."
        if not payload.guild_id or payload.user_id == self.bot.user.id:
            return

        roles = self.roles_from_payload(payload)
        if roles:
            await self.bot.get_guild(payload.guild_id).get_member(
                payload.user_id
            ).add_roles(
                *roles,
                reason=f"Role Kiosk {payload.message_id}",
            )

    @Blimp.Cog.listener()
    async def on_raw_reaction_remove(self, payload: discord.RawReactionActionEvent):
        "On reaction removal, check if we should remove roles and do so."
        if not payload.guild_id or payload.user_id == self.bot.user.id:
            return

        roles = self.roles_from_payload(payload)
        if roles:
            await self.bot.get_guild(payload.guild_id).get_member(
                payload.user_id
            ).remove_roles(
                *roles,
                reason=f"Role Kiosk {payload.message_id}",
            )
