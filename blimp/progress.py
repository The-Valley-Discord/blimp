import asyncio
from typing import Any, Callable, Dict, Optional, Tuple

import discord
from discord.ext import commands

from .cogs.alias import find_aliased_channel_id
from .customizations import Blimp, maybe


class Progress:
    """A Progress instance represents an in-progress interaction with the user based on a single
    embedded message that updates as the user progresses through the "script" of the interaction."""

    def __init__(self, ctx: Blimp.Context, title: str, description: str):
        self.ctx = ctx
        self.embed = discord.Embed(
            color=ctx.Color.AUTOMATIC_BLUE,
            title=title,
            description="\n".join([f"> {line}" for line in description.splitlines()])
            + f"\n\n*Cancel at any time by replying `cancel{self.ctx.bot.suffix}`. "
            "Otherwise, this will time out after five minutes without user input.*",
        )
        self.message = None

    async def start(self):
        "Begin the interaction by post the message."

        self.message = await self.ctx.send(embed=self.embed)

    async def add_stage(self, name: str, value: str):
        "Confirm that this part of the interaction has completed and add a new stage."

        self.embed.add_field(name=name, value=value, inline=False)
        await self.message.edit(embed=self.embed)

    async def edit_last_stage(
        self, name: Optional[str], value: Optional[str], inline=Optional[bool]
    ):
        "Edit the last stage's field to e.g. signal completion."

        field = self.embed.fields[-1]
        self.embed.remove_field(len(self.embed.fields) - 1)
        self.embed.add_field(
            name=name or field.name, value=value or field.value, inline=inline
        )
        await self.message.edit(embed=self.embed)

    async def wait_for(self, transformer: Callable):
        """Wait for messages from the current user in the current channel until one appears such
        that if its content is processed with `transformer(msg.content)`, `transformer` returns a
        value that's not None. That value will be returned. `transformer` should not have side
        effects."""

        def predicate(msg: discord.Message):
            if not (msg.channel == self.ctx.channel and msg.author == self.ctx.author):
                return False

            if msg.content == "cancel!":
                return True

            return transformer(msg.content) is not None

        try:
            message = await self.ctx.bot.wait_for(
                "message",
                check=predicate,
                timeout=300.0,
            )

            if message.content == f"cancel{self.ctx.bot.suffix}":
                self.embed.color = self.ctx.Color.BAD
                await self.add_stage("⛔ Canceled", "No further input will be accepted.")
                return None

            return transformer(message.content)

        except asyncio.TimeoutError:
            self.embed.color = self.ctx.Color.BAD
            await self.add_stage("⛔ Timeout", "No further input will be accepted.")
            return None

    async def confirm_execute(self, command: str):
        """A shorthand method that:
        - Adds a stage that requests confirmation to execute `command`
        - Executes `command` if the user inputs a true bool"""

        await self.add_stage(
            "➡️ Confirm",
            f"**Confirm that you want this command issued in your name:**\n{command}",
        )
        do_it = await self.wait_for(wait_for_bool())
        if do_it is None:
            return

        if do_it:
            await self.ctx.invoke_command(command)
            self.embed.color = self.ctx.Color.GOOD
            await self.edit_last_stage("✅ Confirm", f"**Executed:**\n{command}", False)
        else:
            self.embed.color = self.ctx.Color.BAD
            await self.edit_last_stage(
                "⛔ Confirm", f"**Didn't execute:**\n{command}", False
            )


class AutoProgress(Progress):
    """AutoProgress offers the same capabilities as `Progress` but also allows you to specify a dict
    at creation time that's used in `start` to obtain initial values from the user without having to
    write out the code yourself. The structure of the `steps` dict is
    ```
    {
        "Key To Show The User": ("Description", transformer_for_wait_for, str),
        "Next Key": ("More Description", another_transformer, displayer)
    }
    ```
    Values are processed by `displayer` before being written into a completed input stage. A good
    default for this is `str` for normal Python behavior.
    `start` returns a dict of the collected values with the same keys as in `steps` or `None`, if
    input fails.
    """

    def __init__(self, *args, steps: Dict[str, Tuple[str, Callable]]):
        super(AutoProgress, self).__init__(*args)
        self.steps = steps

    async def start(self) -> Optional[Dict[str, Any]]:
        await super(AutoProgress, self).start()
        return await self.proceed(self.steps)

    async def proceed(
        self, steps: Dict[str, Tuple[str, Callable]]
    ) -> Optional[Dict[str, Any]]:
        "Ask the user to input the `steps` in order of definition."
        result = {}
        for key, value in steps.items():
            desc, transformer, displayer = value
            await self.add_stage(f"➡️ {key}", desc)
            user_input = await self.wait_for(transformer)
            if user_input is None:
                return

            await self.edit_last_stage(
                f"✅ {key}",
                displayer(user_input),
                True,
            )
            result[key] = user_input

        return result


def wait_for_channel(
    ctx: Blimp.Context,
) -> Callable[[str], Optional[discord.TextChannel]]:
    "Returns a `Progress.wait_for` transformer that matches text channels."

    def impl(string: str) -> Optional[discord.TextChannel]:
        aliased_channel = maybe(
            lambda: find_aliased_channel_id(ctx, string), commands.BadArgument
        )
        if aliased_channel:
            return ctx.bot.get_channel(aliased_channel)

        return discord.utils.find(
            lambda c: string == str(c.id) or string == c.mention or string == c.name,
            ctx.guild.channels,
        )

    return impl


def wait_for_number() -> Callable[[str], Optional[int]]:
    "Returns a `Progress.wait_for` transformer that matches numbers."

    def impl(string: str) -> Optional[int]:
        return maybe(lambda: int(string), ValueError)

    return impl


def wait_for_bool() -> Callable[[str], Optional[int]]:
    """Returns a `Progress.wait_for` transformer that matches booleans (somewhat naturally expressed
    ones too)."""

    def impl(string: str) -> Optional[bool]:
        comp = string.casefold()
        if comp in ("yes", "y", "true", "1", "#t", "oui"):
            return True

        if comp in ("no", "n", "false", "0", "-1", "#f"):
            return False

    return impl
