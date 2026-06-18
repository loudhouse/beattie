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
    pattern = re.compile(r"https?://(?:www\.)?inkbunny\.net/(?:s/(\d+)|gallery/.*submissions/(\d+))")

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

        url = "https://inkbunny.net/api_login.php"
        async with self.get(url, method="POST", params=self.login) as resp:
            data = resp.json()
            if "sid" not in data:
                raise RuntimeError("Inkbunny login failed")
            self.sid = data["sid"]

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
        params = {"sid": self.sid, "submission_ids": submission_id}
        
        async with self.get(api_url, params=params) as resp:
            data = resp.json()
            
        submission = data.get("submissions", [{}])[0]
        
        # 1. Author
        queue.author = submission.get("username")
        
        # 2. Images (Original Size)
        # The API returns an array of 'files' with 'file_url_full'
        for file in submission.get("files", []):
            if url := file.get("file_url_full"):
                queue.push_file(url, filename=file.get("file_name"))
            
        # 3. Title
        if title := submission.get("title"):
            queue.push_text(title, bold=True)
            
        # 4. Description (Inkbunny API doesn't provide this in this endpoint, 
        # but you can use keywords or other metadata if needed)
        # Note: Your raw JSON did not contain a 'description' field.
            
        queue.link = f"https://inkbunny.net/s/{submission_id}"