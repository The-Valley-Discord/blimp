import json
import re
from typing import List, Union

import discord
from discord.ext import commands
from discord.ext.commands import UserInputError

from customizations import Blimp
from .alias import MaybeAliasedMessage


class RoleKiosk(Blimp.Cog):
    """*Handing out fancy badges.*
    Role Kiosks allow you to have members assign roles to themselves
    by reacting to a message with emoji. To modify role kiosks, you both
    need to be able to manage the server and all roles you want to offer."""

    @commands.group()
    async def kiosk(self, ctx: Blimp.Context):
        "Manage your server's role kiosks."

    @commands.command(parent=kiosk)
    async def update(
        self,
        ctx: Blimp.Context,
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
            emoji_id = re.search(r"(\d{10,})>?$", emoji)
            if emoji_id:
                emoji = int(emoji_id[1])

            result.append((emoji, role))

        if len(result) == 0:
            raise UserInputError("Expected arguments :emoji: role :emoji: role...")
        if len(result) > 20:
            raise UserInputError("Can't use more than 20 reactions per kiosk.")

        user_failed_roles = []
        bot_failed_roles = []
        for _, role in result:
            if not ctx.privileged_modify(role):
                user_failed_roles.append(role)
            if not ctx.me.top_role > role:
                bot_failed_roles.append(role)

        if user_failed_roles:
            await ctx.reply(
                "*how promethean,*\n"
                "*gifting roles you don't control.*"
                "*yet I must decline.*",
                subtitle="You can't manage these roles: "
                + " ".join([r.name for r in user_failed_roles]),
                color=ctx.Color.BAD,
            )
            return

        if bot_failed_roles:
            await ctx.reply(
                "*despite best efforts,*\n"
                "*this kiosk is doomed to fail,*\n"
                "*its roles beyond me.*",
                subtitle="The bot can't manage these roles: "
                + " ".join([r.name for r in bot_failed_roles]),
                color=ctx.Color.BAD,
            )
            return

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
                value="\n".join(
                    [
                        f"{d[0]} {msg.guild.get_role(d[1]).mention}"
                        for d in json.loads(old["data"])
                    ]
                ),
            )

        log_embed.add_field(
            name="New",
            value="\n".join(
                [f"{d[0]} {msg.guild.get_role(d[1]).mention}" for d in result]
            ),
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
    async def delete(
        self, ctx: Blimp.Context, msg: MaybeAliasedMessage,
    ):
        "Delete a role kiosk (but not the message)."

        if not ctx.privileged_modify(msg.guild):
            return

        cursor = ctx.database.execute(
            "DELETE FROM rolekiosk_entries WHERE oid=:oid",
            {"oid": ctx.objects.by_data(m=[msg.channel.id, msg.id])},
        )
        if cursor.rowcount == 0:
            await ctx.reply(
                "*trying to comply*\n"
                "*I searched all the kiosks known*\n"
                "*that one's still foreign*",
                subtitle="That message isn't a role kiosk.",
                color=ctx.Color.I_GUESS,
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
                *roles, reason=f"Role Kiosk {payload.message_id}",
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
                *roles, reason=f"Role Kiosk {payload.message_id}",
            )
