from __future__ import annotations

import asyncio
import random
import re
import string
from typing import TYPE_CHECKING

import httpx
from lxml import html

from ..database_types import TextLength
from ..selectors import og
from .site import Site

if TYPE_CHECKING:
    from ..context import CrosspostContext
    from ..queue import FragmentQueue


AUTHOR_PATTERN = re.compile(r"furaffinity\.net/art/(\w+)/")
OG_IMAGE = og("image")
OG_TITLE = og("title")
OG_DESCRIPTION = og("description")
MIRRORS = ("xfuraffinity.net", "fxraffinity.net")
NOT_FOUND_MARKERS = ("not found", "could not generate")

BROWSER_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:141.0)"
    " Gecko/20100101 Firefox/141.0"
)

IMAGE_PROXY_RETRIES = 3


class FurAffinity(Site):
    name = "furaffinity"
    pattern = re.compile(
        r"https?://(?:www\.)?(?:[fv]?x)?f[ux]raffinity\.net/view/(\d+)",
    )

    async def handler(self, _ctx: CrosspostContext, queue: FragmentQueue, sub_id: str):
        for host in MIRRORS:
            if result := await self.try_mirror(host, sub_id):
                break
        else:
            queue.push_text(
                "Couldn't find this FurAffinity post. It may have been"
                " deleted, be restricted to logged-in users, or the embed"
                " mirrors this bot relies on may be down.",
                quote=False,
                force=True,
            )
            return

        url, title, description = result

        if m := AUTHOR_PATTERN.search(url):
            queue.author = m.group(1)

        if data := await self.download_image(url):
            frag = queue.push_file(url)
            frag.file_bytes = data
            frag.dl_task = asyncio.get_event_loop().create_future()
            frag.dl_task.set_result(None)
            if frag.postprocess is not None:
                await frag.postprocess(frag)
        else:
            queue.push_text(url, quote=False, escape=False, force=True)

        if title:
            queue.push_text(title, bold=True)
        if description:
            queue.push_text(description, length=TextLength.LONG)

    async def try_mirror(
        self,
        host: str,
        sub_id: str,
    ) -> tuple[str, str | None, str | None] | None:
        link = f"https://{host}/view/{sub_id}?full"
        async with self.get(link, error_for_status=False) as resp:
            if resp.status_code != 200:
                return None
            root = html.document_fromstring(resp.content, self.cog.parser)

        titles = root.xpath(OG_TITLE)
        title = titles[0].get("content") if titles else None
        if title and title.strip().lower() in NOT_FOUND_MARKERS:
            return None

        images = root.xpath(OG_IMAGE)
        if not images or not (image := images[0].get("content")):
            return None

        descs = root.xpath(OG_DESCRIPTION)
        description = descs[0].get("content") if descs else None

        return image, title, description

    async def download_image(self, url: str) -> bytes | None:
        if self.cog.proxies:
            if data := await self.download_via_proxy(url):
                return data

        async with self.get(url, use_browser_ua=True, error_for_status=False) as resp:
            if resp.status_code == 200:
                return resp.content

        return None

    async def download_via_proxy(self, url: str) -> bytes | None:
        proxies = self.cog.proxies

        for _ in range(IMAGE_PROXY_RETRIES):
            proxy = random.choice(proxies)
            if proxy["type"] != "smartproxy":
                continue

            session = "".join(
                random.choices(string.ascii_lowercase + string.digits, k=6),
            )
            proxy_url = (
                f"http://{proxy['user']}-session-{session}:"
                f"{proxy['password']}@{proxy['endpoint']}"
            )
            transport = httpx.AsyncHTTPTransport(proxy=proxy_url)

            try:
                async with httpx.AsyncClient(
                    transport=transport,
                    follow_redirects=True,
                    timeout=30,
                ) as client:
                    resp = await client.get(
                        url,
                        headers={"User-Agent": BROWSER_USER_AGENT},
                    )
            except httpx.HTTPError:
                continue

            if resp.status_code == 200:
                return resp.content

        return None