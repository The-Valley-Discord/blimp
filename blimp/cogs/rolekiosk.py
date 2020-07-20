from typing import List, Union
import json

import discord
from discord.ext import commands
from discord.ext.commands import UserInputError

from bot import BlimpCog
from context import BlimpContext
from converters import MaybeAliasedMessage


class RoleKiosk(BlimpCog):
    """
    Handing out fancy badges.
    """

    @commands.group()
    async def kiosk(self, ctx: BlimpContext):
        """
        Manage your guild's role kiosks.
        """

    @commands.command(parent=kiosk)
    async def update(
        self,
        ctx: BlimpContext,
        msg: MaybeAliasedMessage,
        args: commands.Greedy[Union[discord.Role, str]],
    ):
        """
        Update a role kiosk, overwriting its setup entirely.
        Target doesn't have to be a kiosk prior to issuing this command.

        [args] means: :emoji1: @Role1 :emoji2: @Role2 :emojiN: @RoleN
        Up to 20 pairs per message, due to Discord limitations.
        """

        if not ctx.privileged_modify(msg.guild):
            return

        result = []
        # iterate over pairs of args
        pairwise = iter(args)
        for (emoji, role) in zip(pairwise, pairwise):
            emoji_id = [ch for ch in emoji if ch.isdigit()]
            if len(emoji_id) != 0:
                emoji = int("".join(emoji_id))

            result.append((emoji, role.id))

        if len(result) == 0:
            raise UserInputError("Expected arguments :emoji: role :emoji: role...")
        if len(result) > 20:
            raise UserInputError("Can't use more than 20 reactions per kiosk.")

        for emoji in [item for item in msg.reactions if item.me]:
            await msg.remove_reaction(
                emoji.emoji, ctx.guild.get_member(ctx.bot.user.id)
            )

        for emoji in [item for item in args if item.__class__ == str]:
            await msg.add_reaction(emoji)

        ctx.database.execute(
            "INSERT OR REPLACE INTO rolekiosk_entries(oid, data) VALUES(:oid,json(:data))",
            {
                "oid": ctx.objects.make_object({"m": [msg.channel.id, msg.id]}),
                "data": json.dumps(result),
            },
        )

        await ctx.reply(f"*Overwrote role kiosk {msg.id}.*")

    @commands.command(parent=kiosk)
    async def delete(
        self, ctx: BlimpContext, msg: MaybeAliasedMessage,
    ):
        """
        Delete a role kiosk (but not the message).
        """

        if not ctx.privileged_modify(msg.guild):
            return

        cursor = ctx.database.execute(
            "DELETE FROM rolekiosk_entries WHERE oid=:oid",
            {"oid": ctx.objects.find_object({"m": [msg.channel.id, msg.id]})},
        )
        if cursor.rowcount == 0:
            raise UserInputError("That message isn't a role kiosk.")

        for emoji in [item for item in msg.reactions if item.me]:
            await msg.remove_reaction(
                emoji.emoji, ctx.guild.get_member(ctx.bot.user.id)
            )

        await ctx.reply(f"*Deleted role kiosk {msg.id}.*")

    def roles_from_payload(
        self, payload: discord.RawReactionActionEvent
    ) -> List[discord.Role]:
        """
        Turn a reaction payload into a list of roles to apply or take away.
        """

        cursor = self.bot.database.execute(
            "SELECT data FROM rolekiosk_entries WHERE oid=:oid",
            {
                "oid": self.bot.get_cog("Objects").find_object(
                    {"m": [payload.channel_id, payload.message_id]}
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

    @BlimpCog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        """
        On reaction creation, check if we should add roles and do so.
        """
        if not payload.guild_id:
            return

        roles = self.roles_from_payload(payload)
        if roles:
            await self.bot.get_guild(payload.guild_id).get_member(
                payload.user_id
            ).add_roles(
                *roles, reason=f"Role Kiosk {payload.message_id}",
            )

    @BlimpCog.listener()
    async def on_raw_reaction_remove(self, payload: discord.RawReactionActionEvent):
        """
        On reaction removal, check if we should remove roles and do so.
        """
        if not payload.guild_id:
            return

        roles = self.roles_from_payload(payload)
        if roles:
            await self.bot.get_guild(payload.guild_id).get_member(
                payload.user_id
            ).remove_roles(
                *roles, reason=f"Role Kiosk {payload.message_id}",
            )
