import asyncio
import re
from enum import Enum, auto
from typing import Any, Optional, Tuple, Union

import discord
from discord.ext import commands

from .cogs.alias import (
    find_aliased_category_id,
    find_aliased_channel_id,
    find_aliased_message_id,
)
from .customizations import Blimp, cid_mid_to_message, maybe


class CanceledError(RuntimeError):
    "The not-quite error that the user has canceled a Wizard (or that it's timed out)."


def display(
    what: Union[
        str,
        int,
        bool,
        discord.CategoryChannel,
        discord.TextChannel,
        discord.Message,
        re.Match,
        discord.Role,
        tuple,
    ],
    no_mentions: bool = False,
) -> str:
    """Display some object for the purposes of Wizards. If used for displaying embed field names,
    no_mentions must be True because they don't support mentions. Most of the options for `what`
    ought to be obvious; re.Match is intended to be the result of an emoji match from
    ProgressII.InputKindOption.EMOJI.parse() while the 2-tuple is intended to be the result of a
    message match from ProgressII.InputKindOption.MESSAGE.parse()."""

    if isinstance(what, (discord.TextChannel, discord.Role)) and not no_mentions:
        return what.mention

    if isinstance(what, re.Match):
        return what[0]

    if isinstance(what, tuple) and len(what) == 2:
        return "Fetching message…"

    return str(what)


class ProgressII:
    "Progress but better."

    class InputKindOption(Enum):
        "A pending input for ProgressII.input()."
        STRING = auto()
        INTEGER = auto()
        BOOL = auto()
        CATEGORY = auto()
        CHANNEL = auto()
        MESSAGE = auto()
        EMOJI = auto()
        ROLE = auto()

        def parse(  # pylint: disable=too-many-return-statements, too-many-branches
            self, ctx: Blimp.Context, text: str
        ) -> Any:
            "Return a meaningful object parsed from `text` based on self's kind or None."

            if self == self.STRING:
                return text

            if self == self.INTEGER:
                return maybe(lambda: int(text), ValueError, None)

            if self == self.BOOL:
                comp = text.casefold()
                if comp in ("yes", "y", "true", "1", "#t", "oui"):
                    return True

                if comp in ("no", "n", "false", "0", "-1", "#f"):
                    return False

                return None

            if self == self.CATEGORY:
                aliased_cat = maybe(
                    lambda: find_aliased_category_id(ctx, text), commands.BadArgument
                )
                if aliased_cat:
                    return ctx.bot.get_channel(aliased_cat)

                return discord.utils.find(
                    lambda c: text == str(c.id) or text == c.mention or text == c.name,
                    ctx.guild.categories,
                )

            if self == self.CHANNEL:
                aliased_channel = maybe(
                    lambda: find_aliased_channel_id(ctx, text), commands.BadArgument
                )
                if aliased_channel:
                    return ctx.bot.get_channel(aliased_cat)

                return discord.utils.find(
                    lambda c: text == str(c.id) or text == c.mention or text == c.name,
                    ctx.guild.channels,
                )

            if self == self.MESSAGE:
                aliased_message = maybe(
                    lambda: find_aliased_message_id(ctx, text), commands.BadArgument
                )
                if aliased_message:
                    return aliased_message

                link_or_shift_click_match = re.search(
                    r"(\d{15,21})[/-](\d{15,21})$", text
                )
                if link_or_shift_click_match:
                    return tuple(
                        [
                            int(link_or_shift_click_match[1]),
                            int(link_or_shift_click_match[2]),
                        ]
                    )

                just_id_match = re.search(r"(\d{15,21})$", text)
                if just_id_match:
                    return tuple([ctx.channel.id, int(just_id_match[1])])

                return None

            if self == self.EMOJI:
                return re.search(r"<a?:([^:]+):(\d+)>", text) or text

            if self == self.ROLE:
                return discord.utils.find(
                    lambda c: text == str(c.id) or text == c.mention or text == c.name,
                    ctx.guild.roles,
                )

            return None

    def __init__(self, ctx: Blimp.Context, title: str, description: str):
        self.ctx = ctx
        self.message = None
        self.input_messages = []
        self.embed = discord.Embed(
            color=ctx.Color.AUTOMATIC_BLUE,
            title=title,
            description="\n".join([f"> {line}" for line in description.splitlines()])
            + "\n\n• Automatic timeout after five minutes without input"
            + f"\n• Cancel at any time using `cancel{ctx.bot.suffix}`"
            + f"\n• Accept default values using `ok{ctx.bot.suffix}`",
        )

    @property
    def fields(self):
        "Shorthand for ProgressII.embed.fields"
        return self.embed.fields

    def add_field(self, name: str, value: str, inline: bool):
        "Shorthand for ProgressII.embed.add_field()"
        self.embed.add_field(name=name, value=value, inline=inline)

    def delete_last_field(self):
        "Removes the last field from self.fields."
        self.embed.remove_field(len(self.embed.fields) - 1)

    def edit_last_field(
        self, name: Optional[str], value: Optional[str], inline: Optional[bool]
    ):
        "Edit the last field. Any value provided as None is left unchanged from the original."
        field = self.fields[len(self.fields) - 1]
        self.delete_last_field()
        self.add_field(
            name=name if name is not None else field.name,
            value=value if value is not None else field.value,
            inline=inline if inline is not None else field.inline,
        )

    async def update(self):
        "Push our version of the embed to discord, creating a new message if it doesn't exist yet."
        if self.message:
            await self.message.edit(embed=self.embed)
        else:
            self.message = await self.ctx.send(embed=self.embed)

    async def input(
        self,
        name: str,
        description: str,
        kind: InputKindOption,
        default: Optional[Any] = None,
    ) -> Any:
        "Accept a value from the user. Raises CanceledError if user cancels or input times out."

        def predicate(msg: discord.Message):
            if not (msg.channel == self.ctx.channel and msg.author == self.ctx.author):
                return False

            if msg.content == f"cancel{self.ctx.bot.suffix}":
                return True

            if default is not None and msg.content == f"ok{self.ctx.bot.suffix}":
                return True

            return kind.parse(self.ctx, msg.content) is not None

        if default and kind == self.InputKindOption.BOOL:
            default = bool(default)

        self.embed.set_footer(text=discord.Embed.Empty)
        if default is not None:
            self.embed.set_footer(
                text=f"↑ Default value, accept with 'ok{self.ctx.bot.suffix}'"
            )

        self.add_field(
            f"➡️ {name}",
            description + (f"\n\n```{default}\n```" if default is not None else ""),
            False,
        )
        await self.update()

        try:
            message = await self.ctx.bot.wait_for(
                "message",
                check=predicate,
                timeout=300.0,
            )

            self.input_messages.append(message)

            if message.content == f"cancel{self.ctx.bot.suffix}":
                self.embed.color = self.ctx.Color.BAD
                self.add_field(
                    "❌ Canceled", "No further input will be accepted.", False
                )
                await self.update()
                raise CanceledError()

            parsed = kind.parse(self.ctx, message.content)

            if default is not None and message.content == f"ok{self.ctx.bot.suffix}":
                parsed = kind.parse(self.ctx, display(default))

            self.edit_last_field(f"✅ {name}", display(parsed), True)

            if kind == self.InputKindOption.MESSAGE:
                try:
                    message = await cid_mid_to_message(self.ctx, parsed)
                    message_link = await self.ctx.bot.represent_object({"m": parsed})
                    self.edit_last_field(None, message_link, None)
                    await self.update()
                    return message
                except discord.HTTPException as ex:
                    self.embed.color = self.ctx.Color.BAD
                    self.edit_last_field(f"❌ {name}", "Unknown message.", None)
                    await self.update()
                    raise CanceledError() from ex

            await self.update()
            return parsed

        except asyncio.TimeoutError as ex:
            self.embed.color = self.ctx.Color.BAD
            self.add_field("❌ Timeout", "No further input will be accepted.", False)
            await self.update()
            raise CanceledError() from ex

    async def input_choice(
        self, name: str, description: str, options: Tuple[str], default: Optional[str]
    ) -> str:
        """Similar to ProgressII.input(), but accept one of a set of String choices instead of
        general data."""

        def predicate(msg: discord.Message):
            if not (msg.channel == self.ctx.channel and msg.author == self.ctx.author):
                return False

            if msg.content == f"cancel{self.ctx.bot.suffix}":
                return True

            if default is not None and msg.content == f"ok{self.ctx.bot.suffix}":
                return True

            return msg.content.casefold() in options

        self.embed.set_footer(text=discord.Embed.Empty)
        if default is not None:
            self.embed.set_footer(
                text=f"↑ Default value, accept with 'ok{self.ctx.bot.suffix}'"
            )

        self.add_field(
            f"➡️ {name}",
            description + (f"\n\n```{default}\n```" if default is not None else ""),
            False,
        )
        await self.update()

        try:
            message = await self.ctx.bot.wait_for(
                "message",
                check=predicate,
                timeout=300.0,
            )

            self.input_messages.append(message)

            if message.content == f"cancel{self.ctx.bot.suffix}":
                self.embed.color = self.ctx.Color.BAD
                self.add_field(
                    "❌ Canceled", "No further input will be accepted.", False
                )
                await self.update()
                raise CanceledError()

            option = message.content

            if default is not None and message.content == f"ok{self.ctx.bot.suffix}":
                option = default

            self.edit_last_field(f"✅ {name}", option, True)

            await self.update()
            return option

        except asyncio.TimeoutError as ex:
            self.embed.color = self.ctx.Color.BAD
            self.add_field("❌ Timeout", "No further input will be accepted.", False)
            await self.update()
            raise CanceledError() from ex

    async def offer_cleanup(self):
        """Ask the user if they want to have all their messages accepted by the kiosk, since the
        last offer to do so, deleted."""

        do_cleanup = await self.input(
            "Cleanup",
            "Should all messages you typed for this Wizard be deleted?",
            self.InputKindOption.BOOL,
            True,
        )
        if do_cleanup:
            with self.ctx.typing():
                for message in self.input_messages:
                    await message.delete()
                self.input_messages = []
        self.delete_last_field()
        await self.update()

    async def confirm_execute(self, command: str):
        "Ask the user if they want to execute a `command` and do so if they agree."

        dewit = await self.input(
            "Confirm",
            f"**Do you want this command executed in your name?**\n{command}",
            self.InputKindOption.BOOL,
            True,
        )

        if dewit:
            with self.ctx.typing():
                await self.ctx.invoke_command(command)
                self.embed.color = self.ctx.Color.GOOD
                self.edit_last_field(None, f"**Executed:**\n{command}", False)
                await self.update()
        else:
            self.embed.color = self.ctx.Color.BAD
            self.edit_last_field("❌ Confirm", f"**Didn't Execute:**\n{command}", False)

        await self.offer_cleanup()
