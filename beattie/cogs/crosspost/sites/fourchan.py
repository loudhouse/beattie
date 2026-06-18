from __future__ import annotations

import io
import re
from typing import TYPE_CHECKING

from lxml import html
import discord

from .site import Site

if TYPE_CHECKING:
    from ..context import CrosspostContext
    from ..queue import FragmentQueue

PATTERN = re.compile(
    r"https?://(?:"
    r"boards\.4chan(?:nel)?\.org/(\w+)/thread/(\d+)"
    r"|(desuarchive\.org|archived\.moe|archiveofsins\.com|boards\.fireden\.net|"
    r"archive\.4plebs\.org|arch\.b4k\.dev|archive\.palanq\.win)"
    r"/(\w+)/thread/(\d+)"
    r")(?:/[^#\s]*)?(?:#q?p?(\d+))?",
)

ARCHIVE_IMAGE_SELECTOR = ".//div[contains(@class, 'thread_image_box')]//a"
ARCHIVE_TEXT_SELECTOR = ".//div[contains(@class, 'text')]"

# Ordered by priority
ARCHIVES: list[tuple[str, frozenset[str]]] = [
    (
        "desuarchive.org",
        frozenset({
            "a", "aco", "an", "c", "cgl", "co", "d", "fit", "g", "gif",
            "his", "int", "k", "m", "mlp", "mu", "q", "qa", "r9k", "tg",
            "trash", "vr", "wsg",
        }),
    ),
    (
        "boards.fireden.net",
        frozenset({
            "cm", "co", "sci", "v", "y"
        }),
    ),
    (
        "arch.b4k.dev",
        frozenset({
            "g", "mlp", "qb", "v", "vg", "vm", "vmg", "vp", "vrpg", "vst"
        }),
    ),
    (
        "archive.palanq.win",
        frozenset({
            "bant", "c", "con", "e", "i", "n", "news", "out", "p", "pw", "qst",
            "toy", "vip", "vp", "vt", "w", "wg", "wsr"
        }),
    ),
    (
        "archive.4plebs.org",
        frozenset({
            "adv", "f", "hr", "o", "pol", "s4s", "sp", "tg", "trv", "tv", "x"
        }),
    ),
    (
        "archiveofsins.com",
        frozenset({
            "aco", "d", "e", "h", "hc", "hm", "hr", "s", "t", "u"
        }),
    ),
    (
        "archived.moe",
        frozenset({
            "3", "a", "aco", "adv", "an", "asp", "b", "bant", "biz", "c",
            "can", "cgl", "ck", "cm", "co", "cock", "con", "d", "diy", "e",
            "f", "fa", "fap", "fit", "fitlit", "g", "gd", "gif", "h", "hc",
            "his", "hm", "hr", "i", "ic", "int", "jp", "k", "lgbt", "lit",
            "m", "mlp", "mlpol", "mo", "mtv", "mu", "n", "news", "o", "out",
            "outsoc", "p", "po", "pol", "pw", "q", "qa", "qb", "qst", "r",
            "r9k", "s", "s4s", "sci", "soc", "sp", "spa", "t", "tg", "toy",
            "trash", "trv", "tv", "u", "v", "vg", "vint", "vip", "vmg",
            "vp", "vr", "vrpg", "vt", "w", "wg", "wsg", "wsr", "x", "xs",
            "y",
        }),
    ),
]


def get_archives(board: str) -> list[str]:
    """Returns a priority-ordered list of all archives that support the given board."""
    return [host for host, boards in ARCHIVES if board in boards]


def fourchan_comment_to_text(comment: str) -> str:
    """Convert a 4chan post's HTML `com` field into plain text."""
    fragment = html.fragment_fromstring(f"<div>{comment}</div>")

    for br in fragment.xpath(".//br"):
        br.tail = "\n" + (br.tail or "")

    for wbr in fragment.xpath(".//wbr"):
        wbr.drop_tag()

    return (fragment.text_content() or "").strip()


def archive_div_to_text(div: html.HtmlElement) -> str:
    """Convert an archive post's `.text` div into plain text."""
    for br in div.xpath(".//br"):
        br.tail = "\n" + (br.tail or "")

    return (div.text_content() or "").strip()


class FourChan(Site):
    name = "4chan"
    pattern = PATTERN

    async def _download_file(
        self,
        ctx: CrosspostContext,
        url: str,
        use_browser_ua: bool = False,
    ) -> discord.File | None:
        """Download a file directly to bypass Cloudflare blocks and attach it locally if safe."""
        if url.startswith("//"):
            url = f"https:{url}"

        try:
            async with self.get(url, use_browser_ua=use_browser_ua, error_for_status=False) as resp:
                if resp.status_code != 200:
                    return None

                file_bytes = resp.content
                file_size = len(file_bytes)
                max_bytes = ctx.guild.filesize_limit if ctx.guild else 25 * 1024 * 1024

                if file_size <= max_bytes:
                    clean_url = url.split("?")[0]
                    filename = clean_url.split("/")[-1]
                    
                    if not filename or "." not in filename:
                        ext = "." + clean_url.rsplit(".", 1)[-1] if "." in clean_url else ".png"
                        filename = f"media{ext}"
                        
                    return discord.File(io.BytesIO(file_bytes), filename=filename)
        except Exception:
            pass
        return None

    async def _send_embed(
        self,
        ctx: CrosspostContext,
        board: str,
        thread: str,
        post: str,
        text: str,
        image_url: str,
        ext: str,
        host: str | None = None,
        use_browser_ua: bool = False,
    ):
        """Constructs an embed matching `chan.py` exactly and sends it."""
        if host and host != "boards.4chan.org":
            if host == "desuarchive.org":
                post_link = f"https://desuarchive.org/{board}/thread/{thread}/#{post}"
            else:
                post_link = f"https://{host}/{board}/thread/{thread}#p{post}"
        else:
            post_link = f"https://boards.4chan.org/{board}/thread/{thread}#p{post}"

        embed = discord.Embed(colour=0x00b300)
        embed.add_field(
            name=f"/{board}/ — Thread: {thread}",
            value=f"[>>{post}]({post_link})",
            inline=False,
        )

        if text:
            if len(text) <= 1024:
                embed.add_field(name="\u200b", value=text, inline=False)
            elif len(text) <= 2048:
                embed.set_footer(text=text)
            else:
                embed.add_field(
                    name="PostERROR",
                    value="Post exceeded character limit (2048)",
                    inline=False,
                )

        discord_file = None
        if image_url:
            discord_file = await self._download_file(ctx, image_url, use_browser_ua)

        if discord_file:
            if ext.lower() != ".webm":
                embed.set_image(url=f"attachment://{discord_file.filename}")
            await ctx.send(file=discord_file, embed=embed)
        else:
            if ext.lower() == ".webm" and image_url:
                await ctx.send(content=image_url, embed=embed)
            elif image_url:
                embed.set_image(url=image_url)
                await ctx.send(embed=embed)
            else:
                await ctx.send(embed=embed)

    async def handler(
        self,
        ctx: CrosspostContext,
        queue: FragmentQueue,
        board_live: str | None,
        thread_live: str | None,
        archive_host: str | None,
        board_archive: str | None,
        thread_archive: str | None,
        post: str | None,
    ):
        board = board_live or board_archive
        thread = thread_live or thread_archive
        assert board is not None
        assert thread is not None
        post = post or thread

        # Tell the main crosspost framework to suppress Discord's default native unfurl embed
        queue.link = f"https://boards.4chan.org/{board}/thread/{thread}#p{post}"
        
        CF_ARCHIVES = {"archived.moe", "archiveofsins.com", "archive.4plebs.org"}

        if archive_host:
            if archive_host in CF_ARCHIVES:
                if await self.from_4chan_html(ctx, board, thread, post, archive_host):
                    return
                    
            if await self.from_archive(ctx, archive_host, board, thread, post):
                return
                
            await ctx.send(f"Post not found on {archive_host} (it may have been deleted before it could be archived).")
            return

        if await self.from_4chan(ctx, board, thread, post):
            return

        if await self.from_4chan_html(ctx, board, thread, post, "boards.4chan.org"):
            return

        hosts = get_archives(board)
        for host in hosts:
            if await self.from_archive(ctx, host, board, thread, post):
                return

        await ctx.send("Post not found on any supported archive (it may never have been archived or was deleted).")

    async def from_4chan(
        self,
        ctx: CrosspostContext,
        board: str,
        thread: str,
        post: str,
    ) -> bool:
        api_url = f"https://a.4cdn.org/{board}/thread/{thread}.json"
        async with self.get(api_url, error_for_status=False) as resp:
            if resp.status_code != 200:
                return False
            data = resp.json()

        for p in data["posts"]:
            if str(p["no"]) == post:
                image_url = ""
                ext = ""
                if tim := p.get("tim"):
                    ext = p['ext']
                    image_url = f"https://i.4cdn.org/{board}/{tim}{ext}"

                text = ""
                if com := p.get("com"):
                    text = fourchan_comment_to_text(com)

                await self._send_embed(
                    ctx, board, thread, post, text, image_url, ext, host="boards.4chan.org", use_browser_ua=False
                )
                return True

        return False
        
    async def from_4chan_html(
        self,
        ctx: CrosspostContext,
        board: str,
        thread: str,
        post: str,
        host: str = "boards.4chan.org",
    ) -> bool:
        """Scrape the live 4chan site HTML directly as an experimental fallback."""
        link = f"https://boards.4chan.org/{board}/thread/{thread}"
        async with self.get(link, use_browser_ua=True, error_for_status=False) as resp:
            if resp.status_code != 200:
                return False
            root = html.document_fromstring(resp.content, self.cog.parser)

        posts = root.xpath(f".//div[@id='p{post}']")
        if not posts:
            return False

        article = posts[0]

        image_url = ""
        ext = ""
        if links := article.xpath(".//a[@class='fileThumb']"):
            if url := links[0].get("href"):
                image_url = url
                if image_url.startswith("//"):
                    image_url = f"https:{image_url}"
                clean_url = image_url.split("?")[0]
                ext = "." + clean_url.rsplit(".", 1)[-1] if "." in clean_url else ""

        text = ""
        if divs := article.xpath(".//blockquote[contains(@class, 'postMessage')]"):
            text = archive_div_to_text(divs[0])

        await self._send_embed(
            ctx, board, thread, post, text, image_url, ext, host=host, use_browser_ua=True
        )
        return True

    async def from_archive(
        self,
        ctx: CrosspostContext,
        host: str,
        board: str,
        thread: str,
        post: str,
    ) -> bool:
        # Checking if host uses structural JSON API first to avoid heavy HTML scraping
        api_url = f"https://{host}/_/api/chan/post/?board={board}&num={post}"
        async with self.get(api_url, use_browser_ua=True, error_for_status=False) as api_resp:
            if api_resp.status_code == 200:
                p_data = api_resp.json()
                image_url = p_data.get("media_link", "")
                text = p_data.get("comment", "")
                
                ext = ""
                if image_url:
                    clean_url = image_url.split("?")[0]
                    ext = "." + clean_url.rsplit(".", 1)[-1] if "." in clean_url else ""
                    
                await self._send_embed(
                    ctx, board, thread, post, text, image_url, ext, host=host, use_browser_ua=True
                )
                return True

        # Fallback to standard scraper path if archive endpoint does not return cleanly
        link = f"https://{host}/{board}/thread/{thread}/"
        async with self.get(link, use_browser_ua=True, error_for_status=False) as resp:
            if resp.status_code != 200:
                return False
            root = html.document_fromstring(resp.content, self.cog.parser)

        articles = root.xpath(f".//article[@id='{post}']")
        if not articles:
            return False

        article = articles[0]

        image_url = ""
        ext = ""
        if links := article.xpath(ARCHIVE_IMAGE_SELECTOR):
            if url := links[0].get("href"):
                image_url = url
                if image_url.startswith("//"):
                    image_url = f"https:{image_url}"
                clean_url = image_url.split("?")[0]
                ext = "." + clean_url.rsplit(".", 1)[-1] if "." in clean_url else ""

        text = ""
        if divs := article.xpath(ARCHIVE_TEXT_SELECTOR):
            text = archive_div_to_text(divs[0])
            
        await self._send_embed(
            ctx, board, thread, post, text, image_url, ext, host=host, use_browser_ua=True
        )
        return True