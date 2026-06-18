from __future__ import annotations

from typing import TYPE_CHECKING

from discord.ext.commands import Cog, Command, MinimalHelpCommand

if TYPE_CHECKING:
    from collections.abc import Mapping


class BHelp(MinimalHelpCommand):
    async def send_bot_help(self, mapping: Mapping[Cog | None, list[Command]]):
        await super().send_bot_help(mapping)
        if ctx := self.context:
            await ctx.send(
                "Wexlercord bot https://github.com/loudhouse/beattie\n"
                "Based on beattie by BeatButton et al https://github.com/BeatButton/beattie"
            )

    def add_subcommand_formatting(self, command: Command):
        fmt = "{0} \N{EN DASH} {1}" if command.short_doc else "{0}"
        self.paginator.add_line(
            fmt.format(
                self.get_command_signature(command),
                command.short_doc,
            ),
        )