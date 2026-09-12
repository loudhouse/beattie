from __future__ import annotations

import re
import toml
from typing import TYPE_CHECKING
from .site import Site

if TYPE_CHECKING:
    from ..context import CrosspostContext
    from ..queue import FragmentQueue

class Inkbunny(Site):
    name = "inkbunny"
    
    pattern = re.compile(
        r"https?://(?:www\.)?inkbunny\.net/"
        r"(?:s/(\d+)|gallery/.*submissions/(\d+)|submissionview\.php\?id=(\d+))(?:-p\d+-)?(?:#.*)?"
    )

    def __init__(self, cog):
        super().__init__(cog)
        self.login = {}
        self.sid = None

    async def load(self) -> None:
        try:
            with open("config/crosspost/inkbunny.toml") as fp:
                self.login = toml.load(fp)
        except FileNotFoundError:
            return

        if hasattr(self, "cog") and hasattr(self.cog, "bot") and hasattr(self.cog.bot, "extra"):
            if sid := self.cog.bot.extra.get("crosspost_inkbunny_sid"):
                self.sid = sid
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
        *args: str
    ) -> None:
        submission_id = next((a for a in args if a), None)
        if not submission_id:
            return

        api_url = "https://inkbunny.net/api_submissions.php"
        
        params = {
            "sid": self.sid, 
            "submission_ids": submission_id,
            "show_description": "yes"
        }
        
        async with self.get(api_url, params=params) as resp:
            data = resp.json()
            
        submissions = data.get("submissions")
        if not submissions:
            queue.push_text("Post not found. It may be private.", quote=False, force=True)
            return
            
        submission = submissions[0]
        
        # 1. Author
        queue.author = submission.get("username")
        
        queue.link = f"https://inkbunny.net/s/{submission_id}"
        
        # 2. Images
        for file in submission.get("files", []):
            if url := file.get("file_url_full"):
                queue.push_file(
                    url, 
                    filename=file.get("file_name"),
                    headers={"Referer": queue.link}
                )
            
        # 3. Title
        if title := submission.get("title"):
            queue.push_text(title, bold=True)
            
        # 4. Description
        if description := submission.get("description"):
            description = description.strip()
            if description:
                queue.push_text(description, escape=False)