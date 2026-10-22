from __future__ import annotations

import re
from typing import TYPE_CHECKING

from beattie.utils.aioutils import aload
from beattie.utils.etc import translate_bbcode

from ..database_types import TextLength
from .site import Site

if TYPE_CHECKING:
    from ..cog import Crosspost
    from ..context import CrosspostContext
    from ..queue import FragmentQueue


class Inkbunny(Site):
    name = "inkbunny"

    pattern = re.compile(
        r"https?://(?:www\.)?inkbunny\.net/"
        r"(?:s/(\d+)|gallery/.*submissions/(\d+)|submissionview\.php\?id=(\d+))(?:-p\d+-)?(?:#.*)?"
    )

    def __init__(self, cog: Crosspost):
        super().__init__(cog)
        self.login = {}
        self.sid = None

    async def load(self) -> None:
        if hasattr(self, "cog") and hasattr(self.cog, "bot") and hasattr(self.cog.bot, "extra"):
            if sid := self.cog.bot.extra.get("crosspost_inkbunny_sid"):
                self.sid = sid
                return

        try:
            self.login = await aload("config/crosspost/inkbunny.toml")
        except FileNotFoundError:
            return

        url = "https://inkbunny.net/api_login.php"
        async with self.get(url, method="POST", params=self.login) as resp:
            data = resp.json()
            if "sid" not in data:
                raise RuntimeError("Inkbunny login failed")
            self.sid = data["sid"]

            if hasattr(self, "cog") and hasattr(self.cog, "bot") and hasattr(self.cog.bot, "extra"):
                self.cog.bot.extra["crosspost_inkbunny_sid"] = self.sid

    async def handler(
        self,
        ctx: CrosspostContext,
        queue: FragmentQueue,
        *args: str,
    ) -> None:
        submission_id = next((a for a in args if a), None)
        if not submission_id:
            return

        api_url = "https://inkbunny.net/api_submissions.php"

        params = {
            "sid": self.sid,
            "submission_ids": submission_id,
            "show_description": "yes",
        }

        async with self.get(api_url, method="POST", params=params) as resp:
            data = resp.json()

        submissions = data.get("submissions")
        if not submissions:
            queue.push_text(
                "Post not found. It may be private.",
                quote=False,
                force=True,
            )
            return

        submission = submissions[0]

        # 1. Author
        queue.author = submission.get("username")

        queue.link = f"https://inkbunny.net/s/{submission_id}"

        # 2. Images
        for file in submission.get("files", []):
            full = file.get("file_url_full")
            screen = file.get("file_url_screen")
            if full and screen:
                queue.push_fallback(full, screen, headers={"Referer": queue.link})
            elif full:
                queue.push_file(
                    full,
                    filename=file.get("file_name"),
                    headers={"Referer": queue.link},
                )

        # 3. Title
        if title := submission.get("title"):
            queue.push_text(title, bold=True)

        # 4. Description
        if description := submission.get("description"):
            description = description.strip()
            if description:
                description = translate_bbcode(description)
                queue.push_text(description, escape=False, length=TextLength.LONG)