from __future__ import annotations

import re
from html import unescape as html_unescape
from typing import TYPE_CHECKING, TypedDict

from discord.utils import find

from .site import Site

if TYPE_CHECKING:
    from ..context import CrosspostContext
    from ..queue import FragmentQueue

    class Response(TypedDict):
        image: Image

    class Image(TypedDict):
        tags: list[str]
        description: str
        source_url: str
        representations: Representations

    class Representations(TypedDict):
        full: str


API_FMT = "https://derpibooru.org/api/v1/json/images/{}"


class Derpibooru(Site):
    name = "derpibooru"
    pattern = re.compile(r"https?://(?:www\.)?derpibooru\.org/images/(\d+)")

    async def handler(
        self,
        _ctx: CrosspostContext,
        queue: FragmentQueue,
        image_id: str,
    ):
        link = API_FMT.format(image_id)
        async with self.cog.get(link) as resp:
            post: Response = resp.json()

        image = post["image"]

        queue.author = find(
            lambda t: t.startswith("artist:"),
            image["tags"],
        )

        queue.push_file(image["representations"]["full"])

        if source := image["source_url"]:
            queue.push_text(html_unescape(source), quote=False, force=True)
