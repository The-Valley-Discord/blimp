import asyncio
from datetime import datetime, timedelta, timezone
from typing import Optional, Union

import discord
from discord.ext import commands, tasks

from ..customizations import Blimp, ParseableTimedelta


class Coops(Blimp.Cog):
    "coöp"

    group = discord.app_commands.Group(name="coop", description="user-managed channels")

    repgroup = discord.app_commands.Group(
        name="rep", description="manage your coop", parent=group
    )

    admingroup = discord.app_commands.Group(
        name="coopadmin",
        description="manage coops",
        default_permissions=discord.Permissions(manage_channels=True),
    )

    async def autocomplete_coops(self, ia: discord.Interaction, current: str):
        return sorted(
            [
                discord.app_commands.Choice(
                    name=f"{row['name']}: {row['description']}"[0:100],
                    value=row["name"],
                )
                for row in self.bot.database.execute(
                    "SELECT * FROM coop_descriptions WHERE server_id = :sid",
                    {"sid": ia.guild.id},
                ).fetchall()
                if not current or (current in row["name"] + row["description"])
            ],
            key=lambda choice: choice.value,
        )[0:25]

    def find_coop(self, server_id: int, name: str):
        if row := self.bot.database.execute(
            "SELECT * FROM coop_descriptions WHERE server_id = :sid AND name = :name",
            {"sid": server_id, "name": name},
        ).fetchone():
            return row
        else:
            return None

    def find_coop_rep_ids(self, thread_id: int):
        rows = self.bot.database.execute(
            "SELECT * FROM coop_reps WHERE thread_id=:tid", {"tid": thread_id}
        ).fetchall()
        return [row["user_id"] for row in rows]

    def is_user_banned(self, user_id: int, thread_id: int):
        if row := self.bot.database.execute(
            "SELECT * FROM coop_bans WHERE user_id = :uid AND thread_id = :tid",
            {"uid": user_id, "tid": thread_id},
        ).fetchone():
            return row
        return False

    class CoopView(discord.ui.View):
        "a paged viewer for coops."

        def __init__(self, pages, title):
            super().__init__(timeout=None)
            self.title = title
            self.pages = pages
            self.index = 0
            if len(pages) == 1:
                self.clear_items()

        def page_to_embed(self):
            e = discord.Embed(
                title=self.title + f" ({self.index+1}/{len(self.pages)})",
                color=Blimp.Context.Color.AUTOMATIC_BLUE
            )
            for item in self.pages[self.index]:
                e.add_field(name=f"#{item['number']} <#{item['thread_id']}>", value=item["description"], inline=False)
            return e

        def disable_enable_buttons(self):
            if len(self.pages) == 1:
                return
            self.prev.disabled = self.index == 0
            self.next.disabled = self.index + 1 == len(self.pages)

        @discord.ui.button(label="←", disabled=True)
        async def prev(self, ia: discord.Interaction, _):
            self.index -= 1
            self.disable_enable_buttons()
            await ia.response.edit_message(embed=self.page_to_embed(), view=self)

        @discord.ui.button(label="→")
        async def next(self, ia: discord.Interaction, _):
            self.index += 1
            self.disable_enable_buttons()
            await ia.response.edit_message(embed=self.page_to_embed(), view=self)

    @group.command()
    @discord.app_commands.autocomplete(search=autocomplete_coops)
    async def info(self, ia: discord.Interaction, search: Optional[str]):
        "view and search all the coops on this server"
        pages = [[]]
        page_i = 0
        coops = self.bot.database.execute(
            "SELECT name, coop_descriptions.thread_id, description, group_concat(user_id) AS reps "
            "FROM coop_descriptions LEFT JOIN coop_reps USING (thread_id) WHERE server_id = :sid "
            "GROUP BY thread_id;",
            {"sid": ia.guild.id},
        ).fetchall()
        coops = sorted(coops, key=lambda row: row["name"])
        if search:
            coops = [
                coop
                for coop in coops
                if search.casefold() in (coop["name"] + coop["description"]).casefold()
            ]
        for (i, row) in enumerate(coops):
            if len(pages[page_i]) == 5:
                page_i += 1
                pages.append([])
            rep_text = "\n**coop rep:** "
            if row["reps"]:
                rep_text += " and ".join(
                    [f"<@{uid}>" for uid in row["reps"].split(",")]
                )
            else:
                rep_text += "no-one"
            pages[page_i].append(
                {
                    "number": i+1,
                    "name": row["name"],
                    "thread_id": row["thread_id"],
                    "description": f"{row['description']}{rep_text}",
                }
            )
        view = self.CoopView(
            pages,
            f"All {len(coops)} coops matching {search} in {ia.guild.name}"
            if search
            else f"All {len(coops)} coops in {ia.guild.name}",
        )
        await ia.response.send_message(
            embed=view.page_to_embed(), view=view, ephemeral=True
        )

    @group.command()
    @discord.app_commands.autocomplete(coop=autocomplete_coops)
    async def subscribe(self, ia: discord.Interaction, coop: str):
        "subscribe to a coop to receive pings about events and news"
        if coop := self.find_coop(ia.guild.id, coop):
            self.bot.database.execute(
                "INSERT INTO coop_subscribers VALUES(:uid, :tid)",
                {"uid": ia.user.id, "tid": coop["thread_id"]},
            )
            await ia.response.send_message(
                f"Subscribed you to {coop['name']}. If the coop reps decide it's time to let you know about something, you'll receive a ping!",
                ephemeral=True,
            )
        else:
            await ia.response.send_message(f"I don't know {coop}.", ephemeral=True)

    @group.command()
    @discord.app_commands.autocomplete(coop=autocomplete_coops)
    async def unsubscribe(self, ia: discord.Interaction, coop: str):
        "unsubscribe to a coop to no longer receive pings"
        if coop := self.find_coop(ia.guild.id, coop):
            self.bot.database.execute(
                "DELETE FROM coop_subscribers WHERE user_id = :uid AND thread_id =  :tid",
                {"uid": ia.user.id, "tid": coop["thread_id"]},
            )
            await ia.response.send_message(
                f"Unsubscribed you from {coop['name']}. You will no longer receive pings for it.",
                ephemeral=True,
            )
        else:
            await ia.response.send_message(f"I don't know {coop}.", ephemeral=True)

    @admingroup.command()
    async def create(
        self,
        ia: discord.Interaction,
        parent_channel: discord.ForumChannel,
        name: str,
        description: str,
    ):
        "create a new coop"
        if self.find_coop(ia.guild.id, name):
            await ia.response.send_message(
                f"A coop called {name} already exists on this server. Please choose a different name.",
                ephemeral=True,
            )
            return
        if len(name) > 100 or len(description) > 800:
            await ia.response.send_message(
                f"Coop names must be shorter than 100 and coop descriptions shorter than 800 characters. Sorry.",
                ephemeral=True,
            )
            return
        coop_thread, coop_message = await parent_channel.create_thread(
            name=name, content=description
        )
        self.bot.database.execute(
            "INSERT INTO coop_descriptions VALUES(:thread_id, :server_id, :name, :description)",
            {
                "thread_id": coop_thread.id,
                "server_id": ia.guild.id,
                "name": name,
                "description": description,
            },
        )
        await self.bot.post_log(
            ia.guild,
            f"{ia.user.mention} created coop {coop_thread.mention} in {parent_channel.mention} "
            f"with description:\n> {description}",
        )
        await ia.response.send_message(
            f"Created coop {coop_thread.mention} in {parent_channel.mention}",
            ephemeral=True,
        )

    @admingroup.command()
    @discord.app_commands.autocomplete(coop=autocomplete_coops)
    async def appoint(
        self, ia: discord.Interaction, coop: str, user_to_appoint: discord.Member
    ):
        "appoint a new member to be coop rep"
        if coop := self.find_coop(ia.guild.id, coop):
            coop_channel = self.bot.get_channel(coop["thread_id"])
            if user_to_appoint.id in self.find_coop_rep_ids(coop["thread_id"]):
                await ia.response.send_message(
                    f"{user_to_appoint.mention} is already a rep of {coop_channel.mention}, "
                    "so you can't appoint them to that position.",
                    ephemeral=True,
                )
                return
            self.bot.database.execute(
                "INSERT INTO coop_reps VALUES(:uid, :tid)",
                {"uid": user_to_appoint.id, "tid": coop["thread_id"]},
            )
            coop_desc = self.bot.database.execute(
                "SELECT * FROM coop_descriptions WHERE thread_id = :tid",
                {"tid": coop["thread_id"]},
            ).fetchone()
            coop_reps = [
                ia.guild.get_member(rep_id)
                for rep_id in self.find_coop_rep_ids(coop["thread_id"])
                if ia.guild.get_member(rep_id)
            ]
            coop_message = [
                m async for m in coop_channel.history(oldest_first=True, limit=1)
            ][0]
            await coop_message.edit(
                content=f"{coop_desc['description']}\n"
                f"**coop rep:** {' and '.join([rep.mention for rep in coop_reps])}"
                + ("everyone" if coop["name"].startswith("anarchy") else "")
            )
            await self.bot.post_log(
                ia.guild,
                f"{ia.user.mention} appointed {user_to_appoint.mention} coop rep of {coop_channel.mention}",
            )
            await ia.response.send_message(
                f"appointed {user_to_appoint.mention} coop rep of {coop_channel.mention}",
                ephemeral=True,
            )
        else:
            await ia.response.send_message(f"I don't know {coop}.", ephemeral=True)

    @admingroup.command()
    @discord.app_commands.autocomplete(coop=autocomplete_coops)
    async def dismiss(
        self,
        ia: discord.Interaction,
        coop: str,
        user_to_dismiss: Optional[discord.User],
        user_id_to_dismiss: Optional[int],
    ):
        "dismiss a member from being coop rep"
        if not user_to_dismiss or user_id_to_dismiss:
            await ia.response.send_message(
                "You need to provide either a user or their user id to dismiss them from being a coop rep.",
                ephemeral=True,
            )
            return
        if coop := self.find_coop(ia.guild.id, coop):
            if user_to_dismiss:
                user_id_to_dismiss = user_to_dismiss.id
            coop_channel = self.bot.get_channel(coop["thread_id"])
            if ia.guild.get_member(user_id_to_dismiss) and not (
                user_id_to_dismiss in self.find_coop_rep_ids(coop["thread_id"])
            ):
                await ia.response.send_message(
                    f"<@{user_id_to_dismiss}> is not a rep of {coop_channel.mention}, "
                    "so you can't dismiss them from that position.",
                    ephemeral=True,
                )
                return

            self.bot.database.execute(
                "DELETE FROM coop_reps WHERE user_id=:uid AND thread_id=:tid",
                {"uid": user_id_to_dismiss, "tid": coop["thread_id"]},
            )
            coop_desc = self.bot.database.execute(
                "SELECT * FROM coop_descriptions WHERE thread_id = :tid",
                {"tid": coop["thread_id"]},
            ).fetchone()
            coop_reps = [
                ia.guild.get_member(rep_id)
                for rep_id in self.find_coop_rep_ids(coop["thread_id"])
                if ia.guild.get_member(rep_id)
            ]
            coop_message = [
                m async for m in coop_channel.history(oldest_first=True, limit=1)
            ][0]
            await coop_message.edit(
                content=f"{coop_desc['description']}\n"
                f"**coop rep:** {' and '.join([rep.mention for rep in coop_reps])}"
                + ("everyone" if coop["name"].startswith("anarchy") else "")
            )
            await self.bot.post_log(
                ia.guild,
                f"{ia.user.mention} dismissed <@{user_id_to_dismiss}> as coop rep of {coop_channel.mention}",
            )
            await ia.response.send_message(
                f"dismissed <@{user_id_to_dismiss}> as coop rep of {coop_channel.mention}",
                ephemeral=True,
            )
        else:
            await ia.response.send_message(f"I don't know {coop}.", ephemeral=True)

    @repgroup.command()
    @discord.app_commands.autocomplete(coop=autocomplete_coops)
    async def ban(
        self,
        ia: discord.Interaction,
        coop: str,
        user_to_coopban: discord.Member,
        reason: str,
        duration: Optional[str],
    ):
        "channel-ban a member from a coop you manage, either indefinitely or for a set duration"
        if (coop := self.find_coop(ia.guild.id, coop)) and (
            ia.user.guild_permissions.manage_channels
            or ia.user.id in self.find_coop_rep_ids(coop["thread_id"])
            or coop["name"].startswith("anarchy")
        ):
            expires = None
            if duration:
                expires = datetime.now(tz=timezone.utc) + (
                    await ParseableTimedelta.convert(None, duration)
                )
            if self.is_user_banned(user_to_coopban.id, coop["thread_id"]):
                await ia.response.send_message(
                    f"{user_to_coopban.mention} is already banned from {coop['name']}.",
                    ephemeral=True,
                )
                return

            await ia.response.defer()
            self.bot.database.execute(
                "INSERT INTO coop_bans VALUES(:uid, :tid, :rep_id, :reason, :expires);",
                {
                    "uid": user_to_coopban.id,
                    "tid": coop["thread_id"],
                    "rep_id": ia.user.id,
                    "reason": reason,
                    "expires": expires,
                },
            )
            await self.bot.post_log(
                ia.guild,
                f"{ia.user.mention} has banned {user_to_coopban.mention} from {coop['name']} for reason:\n"
                + f"> {reason}"
                + (
                    f"\nThis ban expires in <t:{int(expires.timestamp())}:R>."
                    if expires
                    else "\nThis ban is until further notice, subject to moderator review."
                ),
            )
            await ia.edit_original_response(
                embed=discord.Embed(
                    color=self.bot.Context.Color.BAD,
                    description=f"### {ia.user} has banned {user_to_coopban} from {coop['name']}.\n"
                    + f"> {reason}"
                    + (
                        f"\nThis ban expires in <t:{int(expires.timestamp())}:R>."
                        if expires
                        else "\nThis ban is until further notice, subject to moderator review."
                    ),
                )
            )
        else:
            await ia.response.send_message(
                f"You can't ban people from {coop}.", ephemeral=True
            )

    @repgroup.command()
    @discord.app_commands.autocomplete(coop=autocomplete_coops)
    async def unban(
        self, ia: discord.Interaction, coop: str, user_to_coopunban: discord.Member
    ):
        "un-channel-ban a member from a coop you manage"
        if (coop := self.find_coop(ia.guild.id, coop)) and (
            ia.user.guild_permissions.manage_channels
            or ia.user.id in self.find_coop_rep_ids(coop["thread_id"])
            or coop["name"].startswith("anarchy")
        ):
            if not self.is_user_banned(user_to_coopunban.id, coop["thread_id"]):
                await ia.response.send_message(
                    f"{user_to_coopunban.mention} isn't banned from {coop['name']}.",
                    ephemeral=True,
                )
                return

            await ia.response.defer()
            self.bot.database.execute(
                "DELETE FROM coop_bans WHERE user_id = :uid AND thread_id = :tid",
                {
                    "uid": user_to_coopunban.id,
                    "tid": coop["thread_id"],
                },
            )
            await self.bot.post_log(
                ia.guild,
                f"{ia.user.mention} has unbanned {user_to_coopunban.mention} from {coop['name']}",
            )
            await ia.edit_original_response(
                embed=discord.Embed(
                    color=self.bot.Context.Color.GOOD,
                    description=f"### {ia.user} has unbanned {user_to_coopunban} from {coop['name']}.",
                )
            )
        else:
            await ia.response.send_message(
                f"You can't unban people from {coop}.", ephemeral=True
            )

    @Blimp.Cog.listener()
    async def on_message(self, msg: discord.Message):
        "delete messages from coop-banned users"
        if not msg.guild or not msg.guild.id in [g.id for g in self.guilds]:
            return
        if (
            ban := self.is_user_banned(msg.author.id, msg.channel.id)
        ) and not msg.author.guild_permissions.manage_messages:
            await msg.delete()
            expires_text = "\nYour ban doesn't have an expiration date."
            if expires := ban["expires"]:
                expires = int(datetime.fromisoformat(expires).timestamp())
                expires_text = (
                    f"\nYour ban will expire automatically in <t:{expires}:R>."
                )
            await msg.author.send(
                f"Sorry, you've been banned from {msg.channel.mention} by a coop rep, <@{ban['rep_id']}>. "
                f"Your message has been deleted, you can find a copy below.{expires_text}"
                " If you have any questions, please contact the moderators.",
                embed=discord.Embed(description=msg.content),
            )

    @Blimp.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        "delete reactions from coop-banned users"
        if not payload.guild_id in [g.id for g in self.guilds]:
            return
        if (
            ban := self.is_user_banned(payload.user_id, payload.channel_id)
        ) and not payload.member.guild_permissions.manage_messages:
            channel = self.bot.get_channel(payload.channel_id)
            msg = channel.get_partial_message(payload.message_id)
            await msg.remove_reaction(payload.emoji, payload.member)

    @tasks.loop(minutes=1)
    async def unban_users(self):
        "regularly unban users whose coop bans have expired"
        now = datetime.now(tz=timezone.utc)
        bans = self.bot.database.execute(
            "SELECT * FROM coop_bans WHERE expires < :now",
            {"now": now},
        ).fetchall()
        self.bot.database.execute(
            "DELETE FROM coop_bans WHERE expires < :now",
            {"now": now},
        )
        for ban in bans:
            channel = self.bot.get_channel(ban["thread_id"])
            await channel.send(
                embed=discord.Embed(
                    color=self.bot.Context.Color.AUTOMATIC_BLUE,
                    description=f"<@{ban['user_id']}>'s ban has expired.",
                )
            )

    @repgroup.command()
    @discord.app_commands.autocomplete(coop=autocomplete_coops)
    async def listbans(self, ia: discord.Interaction, coop: str):
        "list the channel-banned members for a coop you manage"
        if (coop := self.find_coop(ia.guild.id, coop)) and (
            ia.user.guild_permissions.manage_channels
            or ia.user.id in self.find_coop_rep_ids(coop["thread_id"])
            or coop["name"].startswith("anarchy")
        ):
            bans = self.bot.database.execute(
                "SELECT * FROM coop_bans WHERE thread_id = :tid",
                {"tid": coop["thread_id"]},
            ).fetchall()

            def format_ban(row):
                expires = None
                if row["expires"]:
                    expires = int(datetime.fromisoformat(row["expires"]).timestamp())
                return (
                    f"**<@{row['user_id']}> — banned by <@{row['rep_id']}>**\n"
                    + f"> {row['reason']}\n"
                    + (
                        f"Ban expires in <t:{expires}:R>."
                        if expires
                        else "Ban doesn't expire."
                    )
                )

            await ia.response.send_message(
                embed=discord.Embed(
                    title=f"Showing {len(bans)} bans for {coop['name']}",
                    description="\n\n".join([format_ban(row) for row in bans]),
                ),
                ephemeral=True,
            )

        else:
            await ia.response.send_message(
                f"You can't view the bans for {coop}.", ephemeral=True
            )

    @repgroup.command()
    @discord.app_commands.autocomplete(coop=autocomplete_coops)
    async def ping(self, ia: discord.Interaction, coop: str):
        "send a ping to all subscribed members of a coop you manage"
        if (coop := self.find_coop(ia.guild.id, coop)) and (
            ia.user.guild_permissions.manage_channels
            or ia.user.id in self.find_coop_rep_ids(coop["thread_id"])
            or coop["name"].startswith("anarchy")
        ):
            await ia.response.defer(ephemeral=True)
            subscribers = sorted(
                [
                    ia.guild.get_member(row["user_id"])
                    for row in self.bot.database.execute(
                        "SELECT * FROM coop_subscribers WHERE thread_id = :tid",
                        {"tid": coop["thread_id"]},
                    )
                    if ia.guild.get_member(row["user_id"])
                ],
                key=lambda member: member.name,
                reverse=True,
            )
            num_subscribers = len(subscribers)
            ping_string = (
                f"Pinging {num_subscribers} coop subscribers for {ia.user.mention}… ||"
            )
            while subscribers:
                ping_string += subscribers.pop().mention + " "
                if len(ping_string) > 1970 or not subscribers:
                    await self.bot.get_channel(coop["thread_id"]).send(
                        ping_string + "||"
                    )
                    ping_string = "||"
            await ia.edit_original_response(
                content=f"Successfully pinged {num_subscribers} subscribers."
            )

        else:
            await ia.response.send_message(
                f"{coop} either doesn't exist or you aren't a rep for it. Sorry.",
                ephemeral=True,
            )

    @repgroup.command()
    @discord.app_commands.autocomplete(coop=autocomplete_coops)
    async def edit(
        self,
        ia: discord.Interaction,
        coop: str,
        new_name: Optional[str],
        new_description: Optional[str],
    ):
        "edit the name and description of a coop you manage"
        if (coop := self.find_coop(ia.guild.id, coop)) and (
            ia.user.guild_permissions.manage_channels
            or ia.user.id in self.find_coop_rep_ids(coop["thread_id"])
            or coop["name"].startswith("anarchy")
        ):
            if not new_name and not new_description:
                await ia.response.send_message(
                    "You haven't tried to change anything.", ephemeral=True
                )
                return
            if new_name and (
                coop["name"].startswith("anarchy")
                and not new_name.startswith("anarchy")
            ):
                await ia.response.send_message(
                    "The anarchy coop's name must start with **anarchy**. That's like, the one rule.",
                    ephemeral=True,
                )
                return
            if new_name and (
                not coop["name"].startswith("anarchy")
                and new_name.startswith("anarchy")
            ):
                await ia.response.send_message(
                    "There can only be one anarchy coop.", ephemeral=True
                )
                return
            if (new_name and len(new_name) > 100) or (
                new_description and len(new_description) > 800
            ):
                await ia.response.send_message(
                    f"Coop names must be shorter than 100 and coop descriptions shorter than 800 characters. Sorry.",
                    ephemeral=True,
                )
                return

            await ia.response.defer(ephemeral=True)
            self.bot.database.execute(
                "UPDATE coop_descriptions SET name = :name, description = :desc WHERE thread_id =:tid",
                {
                    "name": new_name or coop["name"],
                    "desc": new_description or coop["description"],
                    "tid": coop["thread_id"],
                },
            )
            coop_channel = self.bot.get_channel(coop["thread_id"])
            if new_name:
                await coop_channel.edit(name=new_name)
            if new_description:
                coop_message = [
                    m async for m in coop_channel.history(oldest_first=True, limit=1)
                ][0]
                coop_reps = [
                    ia.guild.get_member(rep_id)
                    for rep_id in self.find_coop_rep_ids(coop["thread_id"])
                    if ia.guild.get_member(rep_id)
                ]
                await coop_message.edit(
                    content=f"{new_description}\n"
                    f"**coop rep:** {' and '.join([rep.mention for rep in coop_reps])}"
                    + ("everyone" if coop["name"].startswith("anarchy") else "")
                )
            await self.bot.post_log(
                ia.guild,
                f"{ia.user.mention} updated coop {coop['name']} {coop_channel.mention}\n"
                + (f"**New name:** {new_name}\n" if new_name else "")
                + (
                    f"**New description:**\n> {new_description}\n"
                    if new_description
                    else ""
                ),
            )
            await ia.edit_original_response(
                content=f"Updated coop {coop_channel.mention}!"
            )
        else:
            await ia.response.send_message(
                f"{coop} either doesn't exist or you aren't a rep for it. Sorry.",
                ephemeral=True,
            )

    class DeleteConfirmView(discord.ui.View):
        def __init__(self, bot, message):
            super().__init__()
            self.bot = bot
            self.message = message

        @discord.ui.button(label="Yes, delete it.", style=discord.ButtonStyle.red)
        async def delete(self, ia, _):
            await ia.response.defer()
            await self.message.delete()
            await asyncio.gather(
                self.bot.post_log(
                    ia.guild,
                    f"{ia.user.mention} deleted message {self.message.id} by "
                    f"{self.message.author.mention} in {self.message.channel.mention}",
                ),
                ia.edit_original_response(
                    content=f"Deleted message by {self.message.author.mention}.",
                    view=None,
                ),
            )

    async def delete(self, ia: discord.Interaction, message: discord.Message):
        "delete a message in a coop you manage"
        if (
            coop := self.bot.database.execute(
                "SELECT * FROM coop_descriptions WHERE thread_id = :tid",
                {"tid": message.channel.id},
            ).fetchone()
        ) and (
            ia.user.id in self.find_coop_rep_ids(coop["thread_id"])
            or coop["name"].startswith("anarchy")
        ):
            await ia.response.send_message(
                content=f"### Are you sure you want to delete this message by {message.author}?\n>>> "
                + message.content[0:1900],
                view=self.DeleteConfirmView(self.bot, message),
                ephemeral=True,
            )
        else:
            await ia.response.send_message(
                f"You can't delete messages here. Sorry.",
                ephemeral=True,
            )

    async def pin(self, ia: discord.Interaction, message: discord.Message):
        "pin/unpin a message in a coop you manage"
        if (
            coop := self.bot.database.execute(
                "SELECT * FROM coop_descriptions WHERE thread_id = :tid",
                {"tid": message.channel.id},
            ).fetchone()
        ) and (
            ia.user.id in self.find_coop_rep_ids(coop["thread_id"])
            or coop["name"].startswith("anarchy")
        ):
            await ia.response.defer(ephemeral=True)
            if message in (await message.channel.pins()):
                await message.unpin()
                await ia.edit_original_response(content=f"Unpinned {message.jump_url}.")
            else:
                await message.pin()
                await ia.edit_original_response(content=f"Pinned {message.jump_url}.")
        else:
            await ia.response.send_message(
                f"You can't pin messages here. Sorry.",
                ephemeral=True,
            )

    def __init__(self, bot):
        super().__init__(bot)
        self.guilds = [
            discord.Object(id=int(i))
            for i in bot.config["coops"]["enabled_guilds"].split(",")
        ]
        self.unban_users.start()
        bot.tree.add_command(self.group, guilds=self.guilds)
        bot.tree.add_command(self.admingroup, guilds=self.guilds)
        bot.tree.context_menu(guilds=self.guilds, name="[coop rep] delete")(self.delete)
        bot.tree.context_menu(guilds=self.guilds, name="[coop rep] pin message")(
            self.pin
        )
