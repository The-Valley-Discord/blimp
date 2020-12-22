import json

import discord
from discord.ext import commands

from ..customizations import Blimp, Unauthorized
from ..progress import (
    AutoProgress,
    display_emoji,
    message_id_to_message,
    wait_for_bool,
    wait_for_category,
    wait_for_channel,
    wait_for_emoji,
    wait_for_message_id,
    wait_for_number,
    wait_for_role,
)


class Wizard(Blimp.Cog):
    "Hey, it looks like you're trying to use BLIMP!"

    @commands.group()
    async def wizard(self, ctx: Blimp.Context):
        "Wizards set up and configure BLIMP features for you in an interactive manner."

    @commands.command(parent=wizard)
    async def board(self, ctx: Blimp.Context):
        "Interactively create or update a Board."

        if not ctx.privileged_modify(ctx.guild):
            raise Unauthorized()

        progress = AutoProgress(
            ctx,
            "Create or Update a Board",
            ctx.bot.get_command("board" + ctx.bot.suffix).help,
            (
                "Channel",
                "Please start by typing which channel you wish to create or edit a Board in.",
                wait_for_channel(ctx),
                lambda channel: channel.mention,
            ),
        )
        results = await progress.start()
        if not results:
            return

        old = ctx.database.execute(
            "SELECT * FROM board_configuration WHERE oid=:oid",
            {"oid": ctx.objects.by_data(tc=results["Channel"].id)},
        ).fetchone()

        if old:
            await progress.edit_last_stage(
                None,
                f"{results['Channel'].mention} — Board configuration already exists, updating.",
                False,
            )
            data = json.loads(old["data"])
            results |= await progress.proceed(
                (
                    "Emoji",
                    "Now, please type which emoji should cause messages to get posted into the "
                    "Board. If you don't care about any particular emoji, answer `any`.\n"
                    f"The current emoji is {ctx.bot.get_emoji(data[0]) or data[0]}.",
                    wait_for_emoji,
                    display_emoji,
                ),
                (
                    "Minimum Count",
                    "Almost done! Please type how many emoji of the same type should be "
                    "required before a message gets reposted.\n"
                    f"The current minimum count is {data[1]}.",
                    wait_for_number(),
                    str,
                ),
                (
                    "Old Messages",
                    "Finally, please type if messages that are older than now should be able "
                    "to get reposted. This may be undesirable e.g. if you are migrating from "
                    "another bot's starboard.\nCurrently, messages "
                    + ("can't " if old["post_age_limit"] else "can ")
                    + "be reposted.",
                    wait_for_bool(),
                    str,
                ),
            )

        else:
            await progress.edit_last_stage(
                None,
                f"{results['Channel'].mention} — No prior configuration, creating new Board.",
                False,
            )
            results |= await progress.proceed(
                (
                    "Emoji",
                    "Now, please type which emoji should cause messages to get posted into the "
                    "Board. If you don't care about any particular emoji, answer `any`.",
                    wait_for_emoji,
                    display_emoji,
                ),
                (
                    "Minimum Count",
                    "Almost done! Please type how many emoji of the same type should be required "
                    "before a message gets reposted.",
                    wait_for_number(),
                    str,
                ),
                (
                    "Old Messages",
                    "Finally, please type if messages that are older than now should be able to "
                    "get reposted. This may be undesirable e.g. if you are migrating from another "
                    "bot's starboard.",
                    wait_for_bool(),
                    str,
                ),
            )

        if not "Old Messages" in results:
            return

        command = (
            f"board{ctx.bot.suffix} update {results['Channel'].mention} "
            f"{display_emoji(results['Emoji'])}  {results['Minimum Count']} "
            + str(not results["Old Messages"])
        )

        await progress.confirm_execute(command)

    @commands.command(parent=wizard)
    async def kiosk(self, ctx: Blimp.Context):
        "Interactively create or update a Kiosk."

        if not ctx.privileged_modify(ctx.guild):
            raise Unauthorized()

        progress = AutoProgress(
            ctx,
            "Create or Update a Kiosk",
            ctx.bot.get_command("kiosk" + ctx.bot.suffix).help,
            (
                "Message",
                "Please start by linking the message you want to edit as a Kiosk.",
                wait_for_message_id(ctx),
                lambda tup: "Fetching message…",
            ),
        )
        results = await progress.start()
        if not results:
            return

        try:
            message = await message_id_to_message(ctx, results["Message"])
        except discord.HTTPException:
            progress.embed.color = ctx.Color.BAD
            await progress.edit_last_stage("❌ Message", "Unknown message.", None)
            return

        message_link = await ctx.bot.represent_object({"m": results["Message"]})

        await progress.edit_last_stage(None, message_link, None)

        row = ctx.database.execute(
            "SELECT * FROM rolekiosk_entries WHERE oid=:oid",
            {"oid": ctx.objects.by_data(m=results["Message"])},
        ).fetchone()

        role_pairs = []
        if row:
            await progress.edit_last_stage(
                None,
                f"{message_link} — Kiosk configuration already exists, updating.",
                False,
            )
            data = json.loads(row["data"])
            results |= await progress.proceed(
                (
                    "Append?",
                    f"The following {len(data)} reaction-role pairs already exist in this kiosk:\n"
                    + ctx.bot.get_cog("Kiosk").render_emoji_pairs(data, " ")
                    + "\nPlease type whether you want to `append` to this list or `overwrite` it.",
                    lambda string: (
                        (string == "append")
                        if string in ("append", "overwrite")
                        else None
                    ),
                    str,
                )
            )
            if "Append?" in results:
                if results["Append?"]:
                    role_pairs.extend(data)
            else:
                return

        else:
            await progress.edit_last_stage(
                None,
                f"{message_link} — No prior configuration, creating new Kiosk.",
                False,
            )

        await progress.add_stage(
            "➡️ Pending Configuration",
            ctx.bot.get_cog("Kiosk").render_emoji_pairs(role_pairs, " ") or "—",
        )

        while True:
            if len(role_pairs) == 20:
                await ctx.reply(
                    "Discord doesn't support more than twenty reactions per message, no further "
                    "pairs will be accepted."
                )
                break

            emoji_key = f"Emoji {len(role_pairs)+1}"
            role_key = f"Role {len(role_pairs)+1}"

            pair_dict = await progress.proceed(
                (
                    emoji_key,
                    "Please type which emoji the Kiosk should offer for the next role.\n"
                    f"Type 'done{ctx.bot.suffix}' to confirm the above configuration and continue.",
                    wait_for_emoji,
                    display_emoji,
                )
            )
            if not emoji_key in pair_dict:
                return
            if f"done{ctx.bot.suffix}" in pair_dict.values():
                break

            pair_dict |= await progress.proceed(
                (
                    role_key,
                    "Please type which role this emoji should grant users.",
                    wait_for_role(ctx),
                    lambda role: role.mention,
                )
            )
            if not role_key in pair_dict:
                return

            progress.delete_last_stage()
            progress.delete_last_stage()

            if not ctx.privileged_modify(pair_dict[role_key]):
                await ctx.reply(
                    f"You can't assign {pair_dict[role_key].mention} yourself. Skipping.",
                    color=ctx.Color.BAD,
                )
                continue

            if pair_dict[role_key] >= ctx.guild.me.top_role:
                await ctx.reply(
                    f"{pair_dict[role_key].mention} is above BLIMP's highest role and therefore "
                    "can't be used in Kiosks. Skipping.",
                    color=ctx.Color.BAD,
                )
                continue

            role_pairs.append(
                (display_emoji(pair_dict[emoji_key]), pair_dict[role_key]),
            )

            await progress.edit_last_stage(
                None,
                ctx.bot.get_cog("Kiosk").render_emoji_pairs(role_pairs, " "),
                False,
            )

        progress.delete_last_stage()
        await progress.edit_last_stage("✅ Pending Configuration", None, None)

        command = f"kiosk{ctx.bot.suffix} update {message.channel.id}-{message.id} " + (
            ctx.bot.get_cog("Kiosk").render_emoji_pairs(role_pairs, " ")
        )

        await progress.confirm_execute(command)

    @commands.command(parent=wizard)
    async def tickets(self, ctx: Blimp.Context):
        "Interactively create or modify a ticket category."

        if not ctx.privileged_modify(ctx.guild):
            raise Unauthorized()

        progress = AutoProgress(
            ctx,
            "Create or Update a Ticket Category",
            ctx.bot.get_command("ticket" + ctx.bot.suffix).help,
            (
                "Category",
                "All Tickets are bound to a category and inherit permissions from it. Please type "
                "in which category you want to create or modify Tickets configuration.",
                wait_for_category(ctx),
                lambda cat: cat.mention,
            ),
        )

        results = await progress.start()
        if not results:
            return

        old_category = ctx.database.execute(
            "SELECT * FROM ticket_categories WHERE category_oid=:category_oid",
            {"category_oid": ctx.objects.by_data(cc=results["Category"].id)},
        ).fetchone()
        if old_category:
            await progress.edit_last_stage(
                None,
                f"{results['Category'].mention}  — Ticket configuration already exists, updating.",
                False,
            )
            results |= await progress.proceed(
                (
                    "Last Ticket Number",
                    "Please type which number the ticket opened most recently has. The next ticket "
                    + "will have a number exactly one higher.\nCurrently set to "
                    + str(old_category["count"])
                    + ".",
                    wait_for_number(),
                    str,
                ),
                (
                    "Transcript Channel",
                    "Please type the channel that transcripts should get posted into when a ticket "
                    "is deleted.\nCurrently they get posted into "
                    + await ctx.bot.represent_object(
                        ctx.objects.by_oid(old_category["transcript_channel_oid"])
                    )
                    + ".",
                    wait_for_channel(ctx),
                    lambda channel: channel.mention,
                ),
                (
                    "DM Transcripts",
                    "Please type if the transcripts should be sent to all users added to the "
                    + "ticket in addition to being posted in the transcript channel.\nCurrently "
                    + "this "
                    + (
                        "is the case."
                        if old_category["dm_transcript"]
                        else "isn't the case."
                    ),
                    wait_for_bool(),
                    str,
                ),
                (
                    "Are Owners Staff?",
                    "Please type if the Ticket's owner should be able to perform staff actions, "
                    "i.e. adding and removing members as well as deleting the ticket.\nCurrently "
                    + "this "
                    + (
                        "is the case."
                        if old_category["can_creator_close"]
                        else "isn't the case."
                    ),
                    wait_for_bool(),
                    str,
                ),
                (
                    "Per-User Limit",
                    "Please type how many Tickets in this category non-staff users are allowed to "
                    + "open at the same time. If you don't want to set a limit, type `unlimited`."
                    + f"\nCurrently {old_category['per_user_limit'] or 'unlimited'}.",
                    lambda s: wait_for_number()(s) or (s if s == "unlimited" else None),
                    str,
                ),
            )
