import json

from discord.ext import commands

from ..customizations import Blimp, Unauthorized
from ..progress import CanceledError, ProgressII, display


class Wizard(Blimp.Cog):
    "Hey, it looks like you're trying to use BLIMP!"

    @commands.group(invoke_without_command=True, case_insensitive=True)
    async def wizard(self, ctx: Blimp.Context):
        """Wizards can help you set up and configure BLIMP features interactively. Each feature has
        its own Wizard. Wizards will ask you questions on what you want to configure, which you can
        answer in individual messages, using the usual BLIMP syntax, and finally present you with a
        command that can be run to achieve the change you wanted."""

        await ctx.invoke_command("help wizard")

    @commands.command(parent=wizard)
    async def board(self, ctx: Blimp.Context):
        "Interactively create or update a Board."

        if not ctx.privileged_modify(ctx.guild):
            raise Unauthorized()

        progress = ProgressII(
            ctx,
            "Create or Update a Board",
            ctx.bot.get_command(f"board{ctx.bot.suffix}").help,
        )
        await progress.update()

        try:
            channel = await progress.input(
                "Channel",
                "Please start by typing the channel you wish to create or edit a Board in.",
                ProgressII.InputKindOption.CHANNEL,
                None,
            )

            old = ctx.database.execute(
                "SELECT * FROM board_configuration WHERE oid=:oid",
                {"oid": ctx.objects.by_data(tc=channel.id)},
            ).fetchone()
            data = None
            if old:
                data = json.loads(old["data"])

            progress.edit_last_field(
                None,
                f"{channel.mention} — "
                + (
                    "Board configuration already exists, updating."
                    if old
                    else "No prior configuration, creating new Board."
                ),
                False,
            )

            emoji = await progress.input(
                "Emoji",
                "Now, please type which emoji should cause messages to get posted into the Board. "
                "You can also type `any`, in which case BLIMP will only consider the reaction "
                "count and not the emoji itself.\n**Note:** A message will only be reposted onto "
                "one Board, so there can be hard-to-predict clashes between an `any` and emoji-"
                "specific Boards running at the same time. You have been warned.",
                ProgressII.InputKindOption.EMOJI,
                (ctx.bot.get_emoji(data[0]) or data[0]) if old else None,
            )

            min_count = await progress.input(
                "Minimum Count",
                "Almost done! Please type how many emoji of the same type should be required "
                "before a message gets reposted.",
                ProgressII.InputKindOption.INTEGER,
                data[1] if old else None,
            )

            old_messages = await progress.input(
                "Old Messages",
                "Finally, please type if messages that are older than now should be able to get "
                "reposted. This may be undesirable e.g. if you are migrating from another bot's "
                "starboard.",
                ProgressII.InputKindOption.BOOL,
                old["post_age_limit"] if old else None,
            )

            command = (
                f"board{ctx.bot.suffix} update {channel.mention} {display(emoji)}  {min_count} "
                # "not" because the actual db value is if they _shouldn't_ be reposted
                + str(not old_messages)
            )

            await progress.confirm_execute(command)

        except CanceledError:
            pass

    @commands.command(parent=wizard)
    async def kiosk(self, ctx: Blimp.Context):
        "Interactively create or update a Kiosk."

        if not ctx.privileged_modify(ctx.guild):
            raise Unauthorized()

        progress = ProgressII(
            ctx,
            "Create or Update a Kiosk",
            ctx.bot.get_command("kiosk" + ctx.bot.suffix).help,
        )
        await progress.update()

        try:
            message = await progress.input(
                "Message",
                "Please start by linking the message you want to edit as a Kiosk.",
                ProgressII.InputKindOption.MESSAGE,
                None,
            )
            cid_mid = [message.channel.id, message.id]

            old = ctx.database.execute(
                "SELECT * FROM rolekiosk_entries WHERE oid=:oid",
                {"oid": ctx.objects.by_data(m=cid_mid)},
            ).fetchone()
            data = None
            if old:
                data = json.loads(old["data"])

            message_link = await ctx.bot.represent_object({"m": cid_mid})
            progress.edit_last_field(
                None,
                f"{message_link} — "
                + (
                    "Kiosk configuration already exists, updating."
                    if old
                    else "No prior configuration, creating new Kiosk."
                ),
                None,
            )

            role_pairs = []

            if old:
                do_append = await progress.input_choice(
                    "Append?",
                    f"The following {len(data)} reaction-role pairs already exist in this kiosk:\n"
                    + ctx.bot.get_cog("Kiosk").render_emoji_pairs(data, " ")
                    + "\nPlease type whether you want to `append` to this list or `overwrite` it.",
                    ("append", "overwrite"),
                    "append",
                )
                if do_append == "append":
                    role_pairs.extend(data)

            progress.add_field(
                "➡️ Pending Configuration",
                ctx.bot.get_cog("Kiosk").render_emoji_pairs(role_pairs, " ") or "—",
                False,
            )

            await progress.update()

            while True:
                if len(role_pairs) == 20:
                    await ctx.reply(
                        "Discord doesn't support more than twenty reactions per message, no "
                        "further pairs will be accepted."
                    )
                    break

                emoji_name = f"Emoji {len(role_pairs)+1}"
                role_name = f"Role {len(role_pairs)+1}"

                emoji = await progress.input(
                    emoji_name,
                    "Please type which emoji the Kiosk should offer for the next role.\n"
                    f"Type `done{ctx.bot.suffix}` to confirm the above configuration and continue.",
                    ProgressII.InputKindOption.EMOJI,
                    None,
                )
                if emoji == f"done{ctx.bot.suffix}":
                    break

                role = await progress.input(
                    role_name,
                    "Please type which role this emoji should grant users.",
                    ProgressII.InputKindOption.ROLE,
                    None,
                )

                progress.delete_last_field()
                progress.delete_last_field()

                if not ctx.privileged_modify(role):
                    await ctx.reply(
                        f"You can't assign {role.mention} yourself. Skipping.",
                        color=ctx.Color.BAD,
                    )
                    continue

                if role >= ctx.guild.me.top_role:
                    await ctx.reply(
                        f"{role.mention} is above BLIMP's highest role and therefore "
                        "can't be used in Kiosks. Skipping.",
                        color=ctx.Color.BAD,
                    )
                    continue

                role_pairs.append(
                    (display(emoji), role),
                )

                progress.edit_last_field(
                    None,
                    ctx.bot.get_cog("Kiosk").render_emoji_pairs(role_pairs, " "),
                    False,
                )

            progress.delete_last_field()
            progress.edit_last_field("✅ Pending Configuration", None, None)

            await progress.confirm_execute(
                f"kiosk{ctx.bot.suffix} update {message.channel.id}-{message.id} "
                + (ctx.bot.get_cog("Kiosk").render_emoji_pairs(role_pairs, " "))
            )

        except CanceledError:
            pass

    @commands.command(parent=wizard)
    async def tickets(self, ctx: Blimp.Context):
        "Interactively create or modify a ticket category."

        if not ctx.privileged_modify(ctx.guild):
            raise Unauthorized()

        progress = ProgressII(
            ctx,
            "Create or Update a Ticket Category",
            ctx.bot.get_command(f"ticket{ctx.bot.suffix}").help,
        )
        await progress.update()

        try:
            category = await progress.input(
                "Category",
                "All Tickets are bound to a category and inherit permissions and settings from it. "
                "Please type which category you want to select for Tickets.",
                ProgressII.InputKindOption.CATEGORY,
                None,
            )

            old = ctx.database.execute(
                "SELECT * FROM ticket_categories WHERE category_oid=:category_oid",
                {"category_oid": ctx.objects.by_data(cc=category.id)},
            ).fetchone()

            progress.edit_last_field(
                None,
                f"{category.mention} — "
                + (
                    "Ticket configuration already exists, updating."
                    if old
                    else "No prior configuration, creating new Ticket category."
                ),
                False,
            )

            skip_category = False

            if old:
                skip_category = await progress.input(
                    "Skip To Classes",
                    "Do you want to skip editing the Category itself (this includes most settings) "
                    "and proceed to editing the Ticket classes offered instead?",
                    ProgressII.InputKindOption.BOOL,
                    True,
                )

            if not skip_category:
                count = await progress.input(
                    "Most Recent Ticket Number",
                    "Please type which number the ticket opened most recently has. The next ticket "
                    "will have a number exactly one higher.",
                    ProgressII.InputKindOption.INTEGER,
                    old["count"] if old else 0,
                )

                transcript_channel = await progress.input(
                    "Transcript Channel",
                    "Please type the channel that transcripts should get posted into when a ticket "
                    "is deleted.",
                    ProgressII.InputKindOption.CHANNEL,
                    ctx.bot.get_channel(ctx.objects.by_oid(old["transcript_channel_oid"])["tc"])
                    if old
                    else None,
                )

                dm_transcript = await progress.input(
                    "DM Transcripts?",
                    "Please type if the transcripts should be sent to all users added to the "
                    "ticket in addition to being posted in the transcript channel.",
                    ProgressII.InputKindOption.BOOL,
                    old["dm_transcript"] if old else None,
                )

                creator_staff = await progress.input(
                    "Are Creators Staff?",
                    "Please type if the Ticket's creator should be able to perform staff actions, "
                    "i.e. adding and removing members as well as deleting the ticket.",
                    ProgressII.InputKindOption.BOOL,
                    old["can_creator_close"] if old else None,
                )

                per_user_limit = await progress.input(
                    "Per-User Limit",
                    "Please type how many Tickets in this category non-staff users are allowed to "
                    "open at the same time. If you don't want to set a limit, type `-1`.",
                    ProgressII.InputKindOption.INTEGER,
                    (old["per_user_limit"] or -1) if old else None,
                )
                if per_user_limit == -1:
                    per_user_limit = ""

                await progress.confirm_execute(
                    f"ticket{ctx.bot.suffix} updatecategory {category.id} {count} "
                    f"{transcript_channel.mention} {creator_staff} {dm_transcript} "
                    f"{per_user_limit}"
                )

            rows = ctx.database.execute(
                "SELECT * FROM ticket_classes WHERE category_oid=:category_oid",
                {"category_oid": ctx.objects.by_data(cc=category.id)},
            ).fetchall()

            ticket_classes = {}
            for row in rows:
                ticket_classes[row["name"]] = row["description"]

            while True:
                progress.embed.color = ctx.Color.AUTOMATIC_BLUE
                choice = await progress.input(
                    "Edit Class",
                    f"This Category has the following {len(ticket_classes)} classes:\n"
                    f"{', '.join([k for k, v in ticket_classes.items()])}\nPlease type which Class "
                    "you'd like to edit.\nCreate a new Class by typing a name that doesn't exist "
                    f"yet.\nTo exit this Wizard, type `done{ctx.bot.suffix}`.",
                    ProgressII.InputKindOption.STRING,
                    None,
                )
                if choice == f"done{ctx.bot.suffix}":
                    progress.delete_last_field()
                    if not ticket_classes:
                        await ctx.reply(
                            "You need at least one Class per Category. Please create one.",
                            color=ctx.Color.BAD,
                        )
                        continue
                    progress.embed.color = ctx.Color.GOOD
                    await progress.offer_cleanup()
                    return

                ticket_classes[choice] = await progress.input(
                    f"Initial Message for {choice}",
                    "Please type which text BLIMP should post if a ticket in this category gets "
                    f"created. [Advanced message formatting]({ctx.bot.config['info']['manual']}"
                    "#advanced-message-formatting) is available.",
                    ProgressII.InputKindOption.STRING,
                    ticket_classes.get(choice),
                )

                progress.delete_last_field()
                progress.delete_last_field()

                await progress.confirm_execute(
                    f"ticket{ctx.bot.suffix} updateclass {category.id} {choice} "
                    f"{ticket_classes[choice]}"
                )

        except CanceledError:
            pass
